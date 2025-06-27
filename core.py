import json
import time
import requests
from websocket import create_connection
import xml.etree.ElementTree as ET
import gzip
import base64
from datetime import datetime
class CDPController:
    def __init__(self, debug_url="http://localhost:9222/json", tab_index=0):
        self.debug_url = debug_url
        self._id = 1
        self.tab_sessions = {}  
        self.current_session_id = None

    def _connect(self):
        tabs = requests.get(self.debug_url).json()
        self.ws_url = tabs[0]["webSocketDebuggerUrl"]
        self.ws = create_connection(self.ws_url)

        # Auto attach để dùng performSearch hoặc các tính năng nâng cao
        self.send("Target.setAutoAttach", {
            "autoAttach": True,
            "waitForDebuggerOnStart": False,
            "flatten": True
        })
    
    def attach_to_tab(self, tab_index):
        tabs = requests.get(self.debug_url).json()
        tab = tabs[tab_index]
        target_id = tab["id"]

        # Nếu đã gắn rồi thì bỏ qua
        if target_id in self.tab_sessions:
            self.current_session_id = self.tab_sessions[target_id]
            return

        # Attach mới
        res = self.send("Target.attachToTarget", {
            "targetId": target_id,
            "flatten": True
        })

        session_id = res["result"]["sessionId"]
        self.tab_sessions[target_id] = session_id
        self.current_session_id = session_id
        print(f"[INFO] Attached to tab {tab_index}, session_id: {session_id}")
    def send(self, method, params=None, session_id=None):
        msg = {
            "id": self._id,
            "method": method,
            "params": params or {}
        }

        # Ưu tiên dùng session_id truyền vào
        if session_id:
            msg["sessionId"] = session_id
        elif hasattr(self, "current_session_id") and self.current_session_id:
            msg["sessionId"] = self.current_session_id

        self.ws.send(json.dumps(msg))
        self._id += 1

        while True:
            res = json.loads(self.ws.recv())
            if res.get("id") == msg["id"]:
                return res

    def navigate(self, url):
        return self.send("Page.navigate", {"url": url})

    def get_root_node(self):
        return self.send("DOM.getDocument")["result"]["root"]

    def query_selector(self, root_node_id, selector):
        return self.send("DOM.querySelector", {
            "nodeId": root_node_id,
            "selector": selector
        })["result"]["nodeId"]

    def focus(self, node_id):
        return self.send("DOM.focus", {"nodeId": node_id})

    def type_text(self, text, delay=0.05):
        for ch in text:
            for event_type in ["keyDown", "keyUp"]:
                self.send("Input.dispatchKeyEvent", {
                    "type": event_type,
                    "text": ch,
                    "unmodifiedText": ch,
                    "key": ch
                })
            time.sleep(delay)

    def click(self, node_id):
        # Lấy toạ độ của node
        self.send("DOM.scrollIntoViewIfNeeded", {"nodeId": node_id})
        res = self.send("DOM.getBoxModel", {"nodeId": node_id})
        if "result" not in res:
            raise ValueError("[ERROR] Không lấy được box model")

        model = res["result"]["model"]
        content = model["content"]
        x = (content[0] + content[2]) / 2
        y = (content[1] + content[5]) / 2

        # Di chuyển chuột đến vị trí và click
        self.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": x,
            "y": y,
            "button": "none"
        })
        self.send("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": 1
        })
        self.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": 1
        })

    def query_selector_by_xpath(self, xpath):
        # Sử dụng DOM.performSearch để tìm theo XPath
        res = self.send("DOM.performSearch", {
            "query": xpath
        })

        if "result" not in res:
            raise ValueError("[ERROR] XPath không tìm thấy")

        search_id = res["result"]["searchId"]
        count = res["result"]["resultCount"]

        # Lấy nodeId đầu tiên khớp
        nodes = self.send("DOM.getSearchResults", {
            "searchId": search_id,
            "fromIndex": 0,
            "toIndex": 1
        })

        if not nodes["result"]["nodeIds"]:
            raise ValueError("[ERROR] Không có nodeId nào từ XPath")

        return nodes["result"]["nodeIds"][0]
    
    def scroll_into_view(self, selector):
        expression = f'document.querySelector("{selector}").scrollIntoView();'
        return self.send("Runtime.evaluate", {"expression": expression})
    
    def type_text_like_user(self, text, delay=0.05):
        for ch in text:
            # Gửi sự kiện keyDown
            self.send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "key": ch,
                "unmodifiedText": ch,
                "text": ch
            })

            # Gửi sự kiện keyUp
            self.send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": ch,
                "unmodifiedText": ch,
                "text": ch
            })

            time.sleep(delay)  # delay giữa các phím như người thật
    
    def clear_input(self):
        # Gửi Ctrl+A
        self.send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": "a",
            "code": "KeyA",
            "windowsVirtualKeyCode": 65,
            "modifiers": 2  # Ctrl
        })
        self.send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "a",
            "code": "KeyA",
            "windowsVirtualKeyCode": 65,
            "modifiers": 2
        })

        time.sleep(0.1)

        # Gửi Backspace
        self.send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": "Backspace",
            "code": "Backspace",
            "windowsVirtualKeyCode": 8
        })
        self.send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "Backspace",
            "code": "Backspace",
            "windowsVirtualKeyCode": 8
        })

        time.sleep(0.1)


    def wait_for_page_load(self, timeout=30):
        self.send("Page.enable")  # Bật nhận sự kiện Page
        start = time.time()
        while time.time() - start < timeout:
            res = json.loads(self.ws.recv())
            if res.get("method") == "Page.loadEventFired":
                return True
        raise TimeoutError("Page load timeout")
    
    def wait_for_selector(self, selector, timeout=10):
        root = self.get_root_node()["nodeId"]
        start = time.time()
        while time.time() - start < timeout:
            res = self.send("DOM.querySelector", {
                "nodeId": root,
                "selector": selector
            })
            node_id = res.get("result", {}).get("nodeId", 0)
            if node_id != 0:
                return node_id
            time.sleep(0.5)
        #raise TimeoutError(f"[ERROR] Timeout waiting for selector: {selector}")
    
    def wait_for_recaptcha_checked(self, timeout=30, poll_interval=0.5):
        """
        Chờ reCAPTCHA được tick (dựa vào grecaptcha.getResponse()), trong khoảng thời gian timeout (giây).
        """
        print("[...] Đang chờ CAPTCHA được tick (qua grecaptcha)...")
        start = time.time()

        while time.time() - start < timeout:
            try:
                res = self.send("Runtime.evaluate", {
                    "expression": 'grecaptcha.getResponse()',
                    "returnByValue": True
                })
                token = res['result']['result']['value']

                if token is not None and token != "":
                    print(f"[...] Kết quả grecaptcha.getResponse(): {res}")
                    print("[✓] CAPTCHA đã được tick!")
                    return True

            except Exception as e:
                print(f"[x] Lỗi khi gọi grecaptcha.getResponse(): {e}")
                if str(e) =="[WinError 10053] An established connection was aborted by the software in your host machine":
                    return False
                if str(e) == "socket is already closed.":
                    return False
            time.sleep(poll_interval)

        raise TimeoutError("Không phát hiện CAPTCHA được tick trong thời gian chờ.")
    
    def attach_to_new_tab(self, old_tab_ids, max_retry=30, delay=1):
        """
        Gắn vào tab mới được mở (tab không nằm trong old_tab_ids).
        Thử lại tối đa max_retry lần, mỗi lần cách nhau delay giây.
        """
        print("[...] Đang chờ tab mới được mở...")

        for attempt in range(max_retry):
            try:
                current_tabs = requests.get(self.debug_url).json()

                for tab in current_tabs:
                    if tab["id"] not in old_tab_ids:
                        print(f"[✓] Tìm thấy tab mới: {tab['id']}")
                        return self.attach_to_tab_by_id(tab["id"])
            except Exception as e:
                print(f"[x] Lỗi khi lấy tab: {e}")

            time.sleep(delay)

        #raise TimeoutError(f"[ERROR] Không tìm thấy tab mới sau {max_retry * delay:.1f} giây.")

    def attach_to_tab_by_id(self, target_id):
        # Nếu đã gắn rồi thì bỏ qua
        if target_id in self.tab_sessions:
            self.current_session_id = self.tab_sessions[target_id]
            return

        res = self.send("Target.attachToTarget", {
            "targetId": target_id,
            "flatten": True
        })
        print(f"[INFO] Attaching to tab ID: {res}")
        session_id = res["result"]["sessionId"]
        self.tab_sessions[target_id] = session_id
        self.current_session_id = session_id
        print(f"[INFO] Attached to tab ID {target_id}, session_id: {session_id}")
        return target_id
    
    def ensure_tab_ready(self):
        self.send("Runtime.enable")
        self.send("Page.enable")
        time.sleep(1)
    
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


