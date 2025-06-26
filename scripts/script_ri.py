

import json
import time
import requests
from websocket import create_connection
import xml.etree.ElementTree as ET
import gzip
import base64
from datetime import datetime
from core import CDPController
def parse_leadlist_xml(xml_path_or_string, from_string=False):
    """
    Đọc XML từ file hoặc chuỗi và trích xuất ID của Root cùng các Lead (ID, CaseKey).

    Args:
        xml_path_or_string (str): Đường dẫn file XML hoặc nội dung XML.
        from_string (bool): True nếu là chuỗi XML.

    Returns:
        tuple: (root_id, list_of_leads), trong đó list_of_leads là list dicts có ID và CaseKey.
    """
    # Load XML
    if from_string:
        tree = ET.ElementTree(ET.fromstring(xml_path_or_string))
    else:
        tree = ET.parse(xml_path_or_string)

    root = tree.getroot()
    ns = {'ns': 'http://risk.regn.net/LeadList'}

    # Lấy Root ID
    root_id = root.attrib.get("ID")

    # Lấy danh sách Lead
    leads = []
    for lead in root.findall(".//ns:Lead", namespaces=ns):
        lead_id = lead.attrib.get("ID")
        case_key = lead.attrib.get("CaseKey")
        leads.append({"id": lead_id, "case_key": case_key})

    return root_id, leads

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
    base64_data = encode_html_to_base64_gzip_xml(html_content)

    # Thời gian crawl dạng giờ Việt Nam AM/PM như bên JS
    crawl_time = datetime.now().strftime("%m/%d/%Y, %I:%M:%S %p")  # giống JS: toLocaleString('en-US', { hour12: true })

    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"{case_id}|{crawl_time}|{base64_data}\n")
        print(f"[✓] Đã ghi {case_id} vào {output_path}")


class ScriptRI:
    def __init__(self):
        self.cdp = CDPController(debug_url="http://localhost:9222/json")
        self.old_tab_id= None  # Biến lưu ID tab cũ
    def connect(self):
        """
        Kết nối đến CDP và gắn vào tab đầu tiên.
        """
        self.cdp._connect()
    def close(self):
        self.cdp.send("Browser.close")
    def clear_cookie(self):
        # 🧹 XÓA COOKIE TRONG 1 GIỜ SAU KHI XONG
        origin = self.cdp.send("Runtime.evaluate", {
                    "expression": "location.origin",
                    "returnByValue": True
                })["result"]["value"]
        self.cdp.send("BrowsingData.remove", {
                        "origin": origin,
                        "dataToRemove": {
                            "cookies": True,
                            "localStorage": True,
                            "cache": True
                        },
                        "options": {
                            "since": int(time.time() - 3600) * 1000
                        }
        })
    def first_run(self, root_id,name_file_input):
        try:
            #taoh file chứa nội dung
            with open(name_file_input.replace(".xml", "_contents.txt"), "w", encoding="utf-8") as f:
                f.write(f'HEADER ROW - CompressionType="GZip" - Encoding="base64" - LeadListGuid="{root_id}\n')
            # Thêm logic chạy script ở đây
            self.cdp.attach_to_tab(0)  # Gắn vào tab đầu tiên
            # Điều hướng
            self.cdp.navigate("https://publicportal.courts.ri.gov/PublicPortal/")
            # Đợi trang tải
            self.cdp.wait_for_page_load()
            #lấy page hiện tại
            old_tabs = requests.get(self.cdp.debug_url).json()
            old_tab_ids = set(tab["id"] for tab in old_tabs if tab.get("type") == "page")
            self.old_tab_id = list(old_tab_ids)[0]
            
            root = self.cdp.get_root_node()["nodeId"]

            #----------- cliclk vào nút Smart Search  -----------    
            node_id_search_smart = self.cdp.query_selector(root, "a.portlet-buttons[href='/PublicPortal/Home/Dashboard/29']")
            print("Node ID node_id_search_smart:", node_id_search_smart)
            # Cuộn đến phần tử
            self.cdp.scroll_into_view("a.portlet-buttons[href='/PublicPortal/Home/Dashboard/29']")
            time.sleep(1)
            self.cdp.click(node_id_search_smart)
            self.cdp.wait_for_page_load()
            return True
        except Exception as e:
            print(f"[ERROR] Lỗi khi khởi tạo script: {e}")
            return False
    def run(self, lead, root_id,name_file_input):
        try:
            #case_key, case_id  = lead
            case_number,_,_,case_id = lead.strip().split("|")  # Lấy phần sau dấu gạch ngang
            print(f"Case Number: {case_number}, Case ID: {case_id}")

            #----------- Nhập vào ô search   ----------- 
            node_id_input_search = self.cdp.wait_for_selector("input#caseCriteria_SearchCriteria.form-control",timeout=10)
            #node_id = self.cdp.query_selector(root, "input#caseCriteria_SearchCriteria.form-control")
            print("Node ID ô search:", node_id_input_search)
            # 3. Focus vào ô input
            self.cdp.focus(node_id_input_search)
            # 4. Gõ văn bản như người dùng
            self.cdp.clear_input()  # Xoá nội dung cũ nếu có
            self.cdp.type_text_like_user(case_number, delay=0.1)

            #----------- cliclk vào nút Summit  -----------    
            # Chờ cho CAPTCHA được check xong
            self.cdp.wait_for_recaptcha_checked(timeout=200)
            print("✅ CAPTCHA đã được check.")

            node_id_Summit = self.cdp.wait_for_selector("input#btnSSSubmit.btn.btn-primary.pull-right",timeout=10)
            #node_id_Summit = self.cdp.query_selector(root, "input#btnSSSubmit.btn.btn-primary.pull-right")
            print("Node ID node_id_Summit:", node_id_Summit)
            #desc = self.cdp.send("DOM.describeNode", {"nodeId": node_id_Summit})
            self.cdp.send("Runtime.evaluate", {
                "expression": 'document.querySelector("input#btnSSSubmit.btn.btn-primary.pull-right").click();'
            })
            self.cdp.wait_for_page_load()

            #----------- cliclk vào bản ghi  -----------
            try:    
                node_id_ban_ghi = self.cdp.wait_for_selector("a.caseLink")
            except Exception as e:
                print(f"[ERROR] Không tìm thấy bản ghi: {e}")
            print("Node ID node_id_ban_ghi:", node_id_ban_ghi)
            if node_id_ban_ghi :
                # Trước khi click, lưu tab cũ
                old_tabs = requests.get(self.cdp.debug_url).json()
                old_ids = set(tab["id"] for tab in old_tabs)
                self.cdp.send("Runtime.evaluate", {
                        "expression": '''
                            const el = document.querySelector("a.caseLink");
                            if (el) {
                                const evt = new MouseEvent("click", {
                                    bubbles: true,
                                    cancelable: true,
                                    view: window
                                });
                                el.dispatchEvent(evt);
                            }
                        '''
                })
                time.sleep(2)

                print("Old tab IDs:", old_ids)
                new_tab_id = self.cdp.attach_to_new_tab(old_ids)
                print("attached to new tab")
                self.cdp.ensure_tab_ready()

                # res = self.cdp.send("DOM.getDocument")
                # root = res["result"]["root"]
                root = self.cdp.get_root_node()
                # Đợi trang load xong
                self.cdp.send("Page.enable")
                    
                # Bước 2: Lấy outerHTML
                print("Root node ID:", root["nodeId"])
                res = self.cdp.send("DOM.getOuterHTML", {
                    "nodeId": root["nodeId"]
                })
                # Debug lỗi nếu thiếu key
                if "outerHTML" not in res:
                    #print("[ERROR] DOM.getOuterHTML failed response:", res)
                    #raise Exception("Could not retrieve outerHTML")
                    html = res["result"]["outerHTML"]
                else:
                    html = res["outerHTML"]
                self.cdp.wait_for_selector("table.roa-table.td-pad-5.ng-scope",timeout=20)
                self.cdp.wait_for_selector("div.roa-pad-bottom.roa-event-event",timeout=20)
                self.cdp.wait_for_selector("div.roa-event-info-hearing-event", timeout=20)
                self.cdp.wait_for_selector("div.roa-pad-bottom.roa-event-bond-setting-history", timeout=20)
                write_case_detail_to_file(case_id, html, name_file_input.replace(".xml", "_contents.txt"))
                self.cdp.send("Target.closeTarget", {
                    "targetId": new_tab_id
                })
        
                return True
            else:
                    root = self.cdp.get_root_node()
                    # Bước 2: Lấy outerHTML
                    print("Root node ID:", root["nodeId"])
                    res = self.cdp.send("DOM.getOuterHTML", {
                        "nodeId": root["nodeId"]
                    })
                    # Debug lỗi nếu thiếu key
                    if "outerHTML" not in res:
                        #print("[ERROR] DOM.getOuterHTML failed response:", res)
                    #raise Exception("Could not retrieve outerHTML")
                        html = res["result"]["outerHTML"]
                    else:
                        html = res["outerHTML"]
                    
                    write_case_detail_to_file(case_id, html, name_file_input.replace(".xml", "_contents.txt"))
                    return True
        except Exception as e:
            print(f"[ERROR] Lỗi khi xử lý lead {lead}: {e}")
            return False

    def click_on_case_link(self):
        
        self.cdp.attach_to_tab_by_id(self.old_tab_id)
        print("Attached back to old tab:", self.old_tab_id)
        node_id_search_smart_2 = self.cdp.wait_for_selector("a#tcControllerLink_0", timeout=20)
        self.cdp.send("Runtime.evaluate", {
            "expression": '''
                document.querySelector("a#tcControllerLink_0")?.click();
            '''
        })
        return True
    #self.cdp.wait_for_page_load()
