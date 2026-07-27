from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mobility_agent.domain.models import RiskProfile, TripCandidate, TripSourceType

CHINA_TZ = ZoneInfo("Asia/Shanghai")

AIRPORT_ALIASES = {
    "首都机场": "PEK",
    "北京首都": "PEK",
    "大兴机场": "PKX",
    "北京大兴": "PKX",
    "浦东机场": "PVG",
    "上海浦东": "PVG",
    "虹桥机场": "SHA",
    "上海虹桥": "SHA",
    "萧山机场": "HGH",
    "杭州萧山": "HGH",
    "遥墙机场": "TNA",
    "济南遥墙": "TNA",
}
KNOWN_AIRPORTS = set(AIRPORT_ALIASES.values())

FLIGHT_PATTERN = re.compile(r"(?<![A-Z0-9])([A-Z0-9]{2})[\s-]?(\d{3,4})(?!\d)", re.I)
IATA_PATTERN = re.compile(r"(?<![A-Z])([A-Z]{3})(?![A-Z])")
TERMINAL_PATTERN = re.compile(r"(?<![A-Z0-9])(T\s?\d{1,2})(?!\d)", re.I)
DATE_PATTERN = re.compile(r"(?:(20\d{2})[年/\-.])?(\d{1,2})[月/\-.](\d{1,2})日?")
TIME_PATTERN = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)(?!\d)")

REDACTION_PATTERNS = (
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)")),
    ("电子邮箱", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("乘机人", re.compile(r"乘机人\s*[:：]?\s*[\u4e00-\u9fff·]{2,20}")),
    (
        "订单或票号",
        re.compile(r"(?i)(订单号|票号|证件号)\s*[:：]?\s*[A-Z0-9\u4e00-\u9fff-]{4,}"),
    ),
)


def redact_sensitive_text(value: str) -> tuple[str, list[str]]:
    redacted = value
    applied: list[str] = []
    for label, pattern in REDACTION_PATTERNS:
        replacement = f"[已遮盖{label}]"
        redacted, count = pattern.subn(replacement, redacted)
        if count:
            applied.append(label)
    return redacted, applied


class TripParser:
    def parse(
        self,
        content: str,
        *,
        source_type: TripSourceType,
        departure_place: str,
        checked_baggage: bool,
        risk_profile: RiskProfile,
        now: datetime | None = None,
    ) -> TripCandidate:
        if source_type is TripSourceType.ICS:
            normalized = self._unfold_ics(content)
            scheduled = self._parse_ics_datetime(normalized)
            searchable = self._ics_searchable_text(normalized)
        else:
            searchable = content
            scheduled = None

        redacted, redactions = redact_sensitive_text(searchable)
        normalized = redacted.upper()
        flight = self._flight_number(normalized)
        airports = self._airports(normalized)
        terminal = self._terminal(normalized)
        scheduled = scheduled or self._date_time(normalized, now=now)

        missing: list[str] = []
        for field_name, value in (
            ("flight_number", flight),
            ("departure_airport", airports[0] if airports else None),
            ("scheduled_departure", scheduled),
        ):
            if value is None:
                missing.append(field_name)

        warnings = []
        if len(airports) < 2:
            warnings.append("未可靠识别目的机场；这不影响机场出发时刻计算。")
        if terminal is None:
            warnings.append("航站楼待确认，机场流程将使用保守默认值。")
        if redactions:
            warnings.append("解析前已遮盖可能的姓名、联系方式、证件或订单字段。")

        confidence = {
            "flight_number": 0.96 if flight else 0.0,
            "departure_airport": 0.92 if airports else 0.0,
            "destination_airport": 0.82 if len(airports) > 1 else 0.0,
            "terminal": 0.9 if terminal else 0.0,
            "scheduled_departure": 0.94 if scheduled else 0.0,
        }
        digest = hashlib.sha256(f"{source_type.value}:{redacted}".encode()).hexdigest()[:16]
        return TripCandidate(
            candidate_id=f"cand-{digest}",
            source_type=source_type,
            source_summary=f"{source_type.value} 导入 · {len(content)} 字符",
            itinerary_source=self._itinerary_source(searchable, source_type),
            flight_number=flight,
            departure_airport=airports[0] if airports else None,
            destination_airport=airports[1] if len(airports) > 1 else None,
            terminal=terminal,
            scheduled_departure=scheduled,
            departure_place=departure_place,
            checked_baggage=checked_baggage,
            risk_profile=risk_profile,
            field_confidence=confidence,
            missing_fields=missing,
            warnings=warnings,
            redactions_applied=redactions,
        )

    @staticmethod
    def _itinerary_source(value: str, source_type: TripSourceType) -> str:
        lowered = value.lower()
        if "携程" in value or "ctrip" in lowered:
            return "ctrip"
        if "航旅纵横" in value or "umetrip" in lowered:
            return "umetrip"
        if any(
            token in value
            for token in (
                "国航",
                "东航",
                "南航",
                "海航",
                "深航",
                "厦航",
                "川航",
                "吉祥航空",
                "春秋航空",
            )
        ):
            return "airline"
        if source_type is TripSourceType.ICS:
            return "calendar"
        return "other"

    @staticmethod
    def _flight_number(value: str) -> str | None:
        match = FLIGHT_PATTERN.search(value)
        return f"{match.group(1)}{match.group(2)}".upper() if match else None

    @staticmethod
    def _terminal(value: str) -> str | None:
        match = TERMINAL_PATTERN.search(value)
        return match.group(1).replace(" ", "").upper() if match else None

    @staticmethod
    def _airports(value: str) -> list[str]:
        matches: list[tuple[int, str]] = []
        for alias, code in AIRPORT_ALIASES.items():
            position = value.find(alias.upper())
            if position >= 0:
                matches.append((position, code))
        for match in IATA_PATTERN.finditer(value):
            code = match.group(1).upper()
            if code in KNOWN_AIRPORTS:
                matches.append((match.start(), code))
        ordered: list[str] = []
        for _, code in sorted(matches):
            if code not in ordered:
                ordered.append(code)
        return ordered

    @staticmethod
    def _date_time(value: str, *, now: datetime | None) -> datetime | None:
        date_match = DATE_PATTERN.search(value)
        time_match = TIME_PATTERN.search(value)
        if not date_match or not time_match:
            return None
        current = (now or datetime.now(CHINA_TZ)).astimezone(CHINA_TZ)
        year = int(date_match.group(1) or current.year)
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        result = datetime(
            year,
            month,
            day,
            int(time_match.group(1)),
            int(time_match.group(2)),
            tzinfo=CHINA_TZ,
        )
        if date_match.group(1) is None and result < current:
            result = result.replace(year=year + 1)
        return result

    @staticmethod
    def _unfold_ics(value: str) -> str:
        return re.sub(r"\r?\n[ \t]", "", value)

    @staticmethod
    def _ics_searchable_text(value: str) -> str:
        fields = []
        for line in value.splitlines():
            if line.upper().startswith(("SUMMARY", "DESCRIPTION", "LOCATION")):
                fields.append(line.split(":", 1)[-1])
        return "\n".join(fields) or value

    @staticmethod
    def _parse_ics_datetime(value: str) -> datetime | None:
        match = re.search(
            r"(?im)^DTSTART(?:;TZID=([^:;\r\n]+))?(?:;VALUE=DATE-TIME)?:"
            r"(\d{8}T\d{4,6}Z?)",
            value,
        )
        if not match:
            return None
        timezone_name, raw = match.groups()
        is_utc = raw.endswith("Z")
        raw = raw.removesuffix("Z")
        pattern = "%Y%m%dT%H%M%S" if len(raw) == 15 else "%Y%m%dT%H%M"
        parsed = datetime.strptime(raw, pattern)
        if is_utc:
            return parsed.replace(tzinfo=UTC).astimezone(CHINA_TZ)
        timezone = CHINA_TZ
        if timezone_name:
            try:
                timezone = ZoneInfo(timezone_name)
            except Exception:
                timezone = CHINA_TZ
        return parsed.replace(tzinfo=timezone)


class LocalOCRService:
    max_bytes = 5 * 1024 * 1024
    supported_content_types = {"image/png", "image/jpeg"}

    def __init__(self, command: str | None, languages: str = "chi_sim+eng") -> None:
        self.command = command
        self.languages = languages

    @property
    def available(self) -> bool:
        return bool(self.command)

    def extract(self, payload: bytes, *, content_type: str) -> str:
        if not self.command:
            raise RuntimeError("本机 OCR 未配置")
        if content_type not in self.supported_content_types:
            raise ValueError("只支持 PNG 或 JPEG 图片")
        if not payload or len(payload) > self.max_bytes:
            raise ValueError("图片必须小于 5 MB")
        if content_type == "image/png" and not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNG 文件签名无效")
        if content_type == "image/jpeg" and not payload.startswith(b"\xff\xd8\xff"):
            raise ValueError("JPEG 文件签名无效")

        suffix = ".png" if content_type == "image/png" else ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix) as candidate:
            candidate.write(payload)
            candidate.flush()
            languages = self._available_languages()
            completed = subprocess.run(
                [
                    self.command,
                    candidate.name,
                    "stdout",
                    "-l",
                    languages,
                    "--psm",
                    "6",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        if completed.returncode != 0:
            raise RuntimeError("OCR 解析失败")
        text = completed.stdout.strip()
        if len(text) < 3:
            raise ValueError("图片中没有识别到可用行程文字")
        return text[:50_000]

    def _available_languages(self) -> str:
        if not self.command:
            return "eng"
        try:
            completed = subprocess.run(
                [self.command, "--list-langs"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "eng"
        available = {
            line.strip()
            for line in completed.stdout.splitlines()
            if line.strip() and not line.startswith("List of")
        }
        requested = [item for item in self.languages.split("+") if item in available]
        return "+".join(requested) or (
            "eng" if "eng" in available else next(iter(available), "eng")
        )


def path_suffix(content_type: str) -> str:
    return Path("image.png" if content_type == "image/png" else "image.jpg").suffix
