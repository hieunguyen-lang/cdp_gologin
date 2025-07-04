from dateutil import parser
from datetime import datetime

import re
from dateutil import parser
from datetime import datetime

def formatdomain_name(input_str: str) -> str:
    formats = [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%B %d, %Y",
        "%d %B %Y %H:%M:%S",
    ]

    input_str = input_str.strip()

    # ⚠️ Sửa chuỗi sai định dạng như: "2025-07-01+0714:50:00"
    # → thành: "2025-07-01T14:50:00+07:00"
    match = re.match(r"(\d{4}-\d{2}-\d{2})\+(\d{2})(\d{2}:\d{2}:\d{2})", input_str)
    if match:
        date_part = match.group(1)
        hour_min_sec = match.group(3)
        tz_hour = match.group(2)
        # Tạo lại chuỗi đúng chuẩn ISO 8601
        input_str = f"{date_part}T{hour_min_sec}+{tz_hour}:00"

    try:
        return parser.parse(input_str).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        for fmt in formats:
            try:
                return datetime.strptime(input_str, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except:
                continue

    raise ValueError(f"❌ Không parse được định dạng time: {input_str}")



print(formatdomain_name("2025-07-01+0714:50:00"))