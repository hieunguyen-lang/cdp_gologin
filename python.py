import json
import time
import requests
from websocket import create_connection
import xml.etree.ElementTree as ET
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
    
    def wait_for_recaptcha_checked(self, timeout=30):
        print("[...] Đang chờ CAPTCHA checkbox được tick...")

        start = time.time()
        while time.time() - start < timeout:
            try:
                # 1. Lấy toàn bộ frame
                frame_tree = self.send("Page.getFrameTree")
                frames = []

                def collect_frames(tree):
                    frames.append(tree["frame"])
                    for child in tree.get("childFrames", []):
                        collect_frames(child)

                collect_frames(frame_tree["frameTree"])

                # 2. Iterate từng frame
                for frame in frames:
                    frame_id = frame["id"]
                    
                    # 3. Tạo isolated world để chạy JS trong context iframe
                    try:
                        world = self.send("Page.createIsolatedWorld", {
                            "frameId": frame_id,
                            "grantUniveralAccess": True
                        })
                        context_id = world["executionContextId"]
                    except:
                        continue

                    # 4. Chạy JS kiểm tra trong context đó
                    res = self.send("Runtime.evaluate", {
                        "expression": '''
                            (function() {
                                const el = document.querySelector(".recaptcha-checkbox-checked");
                                return !!el;
                            })();
                        ''',
                        "contextId": context_id
                    })

                    if res.get("result", {}).get("value") is True:
                        print("[✓] CAPTCHA đã được tick trong frame:", frame_id)
                        return True

            except Exception as e:
                pass

            time.sleep(0.5)

        raise TimeoutError("Không phát hiện CAPTCHA được tick trong thời gian chờ.")
    
    def attach_to_new_tab(self, old_tab_ids):
            # Lấy danh sách tab hiện tại
            current_tabs = requests.get(self.debug_url).json()
            for tab in current_tabs:
                if tab["id"] not in old_tab_ids:
                    
                    return self.attach_to_tab_by_id(tab["id"])
            raise ValueError("[ERROR] Không tìm thấy tab mới")
        #raise TimeoutError("[×] Hết thời gian chờ CAPTCHA giao diện.")

    def attach_to_tab_by_id(self, target_id):
        # Nếu đã gắn rồi thì bỏ qua
        if target_id in self.tab_sessions:
            self.current_session_id = self.tab_sessions[target_id]
            return

        res = self.send("Target.attachToTarget", {
            "targetId": target_id,
            "flatten": True
        })

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

cdp = CDPController(debug_url="http://localhost:9222/json")
cdp._connect()
cdp.attach_to_tab(0)  # Gắn vào tab đầu tiên
# Điều hướng
cdp.navigate("https://publicportal.courts.ri.gov/PublicPortal/")
# Đợi trang tải
cdp.wait_for_page_load()
#lấy page hiện tại
old_tabs = requests.get(cdp.debug_url).json()
old_tab_ids = set(tab["id"] for tab in old_tabs if tab.get("type") == "page")
old_tab_id = list(old_tab_ids)[0]
 
root = cdp.get_root_node()["nodeId"]

#----------- cliclk vào nút Smart Search  -----------    
node_id_search_smart = cdp.query_selector(root, "a.portlet-buttons[href='/PublicPortal/Home/Dashboard/29']")
print("Node ID node_id_search_smart:", node_id_search_smart)
# Cuộn đến phần tử
cdp.scroll_into_view("a.portlet-buttons[href='/PublicPortal/Home/Dashboard/29']")
time.sleep(1)
cdp.click(node_id_search_smart)
cdp.wait_for_page_load()
root_id, lead_ids = parse_leadlist_xml("RIJPDF_062025_CASENUMBER_00034_1YR_20250603.xml")
print("Root ID:", root_id)
for item in lead_ids:
    case_number, _, _ = item['case_key'].split("|")

    #----------- Nhập vào ô search   ----------- 
    node_id_input_search = cdp.wait_for_selector("input#caseCriteria_SearchCriteria.form-control",timeout=10)
    #node_id = cdp.query_selector(root, "input#caseCriteria_SearchCriteria.form-control")
    print("Node ID ô search:", node_id_input_search)
    # 3. Focus vào ô input
    cdp.focus(node_id_input_search)
    # 4. Gõ văn bản như người dùng
    cdp.clear_input()  # Xoá nội dung cũ nếu có
    cdp.type_text_like_user(case_number, delay=0.1)

    #----------- cliclk vào nút Summit  -----------    
    # Chờ cho CAPTCHA được check xong
    cdp.wait_for_recaptcha_checked(timeout=30)
    print("✅ CAPTCHA đã được check.")

    node_id_Summit = cdp.wait_for_selector("input#btnSSSubmit.btn.btn-primary.pull-right",timeout=10)
    #node_id_Summit = cdp.query_selector(root, "input#btnSSSubmit.btn.btn-primary.pull-right")
    print("Node ID node_id_Summit:", node_id_Summit)
    #desc = cdp.send("DOM.describeNode", {"nodeId": node_id_Summit})
    cdp.send("Runtime.evaluate", {
        "expression": 'document.querySelector("input#btnSSSubmit.btn.btn-primary.pull-right").click();'
    })
    cdp.wait_for_page_load()

    #----------- cliclk vào bản ghi  -----------    
    node_id_ban_ghi = cdp.wait_for_selector("a.caseLink")
    print("Node ID node_id_ban_ghi:", node_id_ban_ghi)
    # Trước khi click, lưu tab cũ
    old_tabs = requests.get(cdp.debug_url).json()
    old_ids = set(tab["id"] for tab in old_tabs)

    cdp.send("Runtime.evaluate", {
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
    new_tab_id = cdp.attach_to_new_tab(old_ids)
    print("attached to new tab")
    cdp.ensure_tab_ready()

    # res = cdp.send("DOM.getDocument")
    # root = res["result"]["root"]
    root = cdp.get_root_node()
    # Bước 2: Lấy outerHTML
    print("Root node ID:", root["nodeId"])
    res = cdp.send("DOM.getOuterHTML", {
        "nodeId": root["nodeId"]
    })
    # Debug lỗi nếu thiếu key
    if "outerHTML" not in res:
        #print("[ERROR] DOM.getOuterHTML failed response:", res)
    #raise Exception("Could not retrieve outerHTML")
        html = res["result"]["outerHTML"]
    else:
        html = res["outerHTML"]
    #print(html)
    with open("output.html", "w", encoding="utf-8") as f:
        f.write(html)
    cdp.send("Target.closeTarget", {
        "targetId": new_tab_id
    })
    cdp.attach_to_tab_by_id(old_tab_id)
    print("Attached back to old tab:", old_tab_id)
    node_id_search_smart_2 = cdp.wait_for_selector("a#tcControllerLink_0", timeout=20)
    cdp.send("Runtime.evaluate", {
        "expression": '''
            document.querySelector("a#tcControllerLink_0")?.click();
        '''
    })
    #cdp.wait_for_page_load()

