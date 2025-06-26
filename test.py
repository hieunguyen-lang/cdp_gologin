import re

import re

def parse_currency_input_int(value):
    """
    Chuyển chuỗi tiền tệ (kể cả có hậu tố k/m, dấu chấm, đ, ₫...) thành số nguyên.
    """
    if not value:
        return 0

    try:
        if isinstance(value, (int, float)):
            return int(value)

        s = str(value).strip().lower().replace(",", ".").replace(" ", "")
        
        # Nếu có hậu tố k/m
        km_match = re.match(r"([\d\.]+)([km])", s)
        if km_match:
            num, suffix = km_match.groups()
            num = float(num)
            if suffix == "k":
                num *= 1_000
            elif suffix == "m":
                num *= 1_000_000
            return int(num)

        # Không có hậu tố → giữ lại toàn bộ số
        digits_only = re.sub(r"[^\d]", "", s)
        return int(digits_only) if digits_only else 0

    except:
        return 0


print(parse_currency_input_int("84.234M"))  # 1.234,56
print(parse_currency_input_int("84.234k"))  # 1.234.560
print(parse_currency_input_int("1.234.506"))  # 1.234     .560.000            
print(parse_currency_input_int("1,234,506")) 