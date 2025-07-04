import json
import undetected_chromedriver as uc
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import xml.etree.ElementTree as ET
import gzip
import base64
from datetime import datetime
def encode_html_to_base64_gzip_xml(html: str, *, uri=None, timestamp=None, other_tags='') -> str:
    """
    Nén HTML bằng gzip + base64, đóng gói vào XML, rồi tiếp tục gzip + base64 toàn bộ XML.
    Trả về chuỗi base64 của XML nén.
    """
    gzipped_html = gzip.compress(html.encode('utf-8'), compresslevel=9)
    base64_html = base64.b64encode(gzipped_html).decode('utf-8')

    def get_timestamp():
        now = datetime.utcnow()
        iso = now.isoformat(timespec='milliseconds') + '0000Z'
        return iso.replace('+00:00', 'Z')

    timestamp = timestamp or get_timestamp()
    uri = uri or "https://casesearch.courts.state.md.us/casesearch/inquiryByCaseNum.jis"

    xml_template = f'''<?xml version="1.0" encoding="utf-16"?>
        <CollectionRecord xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
        <Uri>{uri}</Uri>
        <TimeStamp>{timestamp}</TimeStamp>
        {other_tags}
        <Base64EncodedGZipCompressedContent>{base64_html}</Base64EncodedGZipCompressedContent>
        </CollectionRecord>
        '''
    gzipped_xml = gzip.compress(xml_template.encode('utf-8'), compresslevel=9)
    final_base64 = base64.b64encode(gzipped_xml).decode('utf-8')
    return final_base64

def write_case_detail_to_file(case_id: str, html_content: str, output_path: str):
    """
    Nén HTML, đóng gói, base64, rồi ghi ra file theo định dạng: id|thời_gian|base64
    """
    print("Nén HTML, đóng gói, base64, rồi ghi ra file theo định dạng: id|thời_gian|base64")
    base64_data = encode_html_to_base64_gzip_xml(html_content)

    # Thời gian crawl dạng giờ Việt Nam AM/PM như bên JS
    crawl_time = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")  # giống JS: toLocaleString('en-US', { hour12: true })

    return f"{case_id.strip()}|{crawl_time.strip()}|{base64_data.strip()}\n"
    
class ScriptOR_multi:  
    def __init__(self, profile_id):
        self.profile_id = profile_id
        self.driver = self.create_undetected_driver(profile_id) 
    def first_run(self, root_id,name_file_input):
            try:
                #taoh file chứa nội dung
                with open(name_file_input.replace(".xml", "_contents.txt"), "w", encoding="utf-8") as f:
                    f.write(f'HEADER ROW - CompressionType="GZip" - Encoding="base64" - LeadListGuid="{root_id}"')
                return True,""
            except Exception as e:
                print(f"[ERROR] Lỗi khi khởi tạo script: {e}")
                return False,f"[ERROR] Lỗi khi khởi tạo script: {e}"
        
    def create_undetected_driver(self,profile_dir: str, headless: bool = False) -> uc.Chrome:
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={os.path.abspath(profile_dir)}")
        options.add_argument("--no-first-run --no-service-autorun --password-store=basic")
        options.add_argument("--disable-blink-features=AutomationControlled")

        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1280,800")

        driver = uc.Chrome(options=options)
        return driver

    
    
    def run(self, lead):
        try:
              # Giả định bạn đã tạo sẵn Selenium driver

            # Điều hướng
            self.driver.get("https://myeclerk.myorangeclerk.com/Cases/Search")

            case_number, case_id = lead.strip().split("|")
            print(f"Case Number: {case_number}, Case ID: {case_id}")
            print("------------Chờ cho CAPTCHA được check xong-----------")

            # ✅ Chờ CAPTCHA được check bằng mắt → delay hoặc chờ nút Search enabled
            try:
                WebDriverWait(self.driver, 200).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[@id="caseSearch"]'))
                )
                print("✅ CAPTCHA đã được check.")
            except:
                print("[ERROR] CAPTCHA chưa check xong.")
                return False,''

            # ✅ Tìm ô input và nhập case_number
            try:
                print("----------- Nhập vào ô search -----------")
                input_elem = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//input[@id="caseNumber"]'))
                )
                input_elem.clear()
                for ch in case_number:
                    input_elem.send_keys(ch)
                    time.sleep(0.1)  # delay giống người dùng
            except Exception as e:
                print(f"[ERROR] Lỗi nhập case number: {e}")
                return False,''

            # ✅ Click nút search
            try:
                print("------------Click nút search-----------")
                search_btn = self.driver.find_element(By.XPATH, '//button[@id="caseSearch"]')
                search_btn.click()
            except Exception as e:
                print(f"[ERROR] Lỗi click search: {e}")
                return False,''

            # ✅ Đợi trang kết quả tải xong
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//table'))
            )

            print("----------- Kiểm tra xem có bản ghi nào không -----------")
            try:
                # Có kết quả
                result_link = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//a[contains(@class, "caseLink")]'))
                )
                result_link.click()
                time.sleep(1)
            except Exception as e:
                print(f"[WARN] Không có bản ghi, lấy HTML hiện tại: {e}")
                data = write_case_detail_to_file(case_id, html, )
                return True, data
            # ✅ Chờ nội dung case detail load
            time.sleep(2)

            # ✅ Lấy full HTML
            html = self.driver.page_source
            write_case_detail_to_file(case_id, html)
            return True,data

        except Exception as e:
            print(f"[ERROR] Lỗi khi xử lý lead {lead}: {e}")
            return False, ''


