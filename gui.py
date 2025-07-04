import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from scripts.script_ri import ScriptRI  
from scripts.script_or import ScriptOR
from scripts.script_or_multi_threads import ScriptOR_multi   # Giả sử bạn có một script OR tương tự
from helpers.helper import Helper
import threading
import queue
# Hàng đợi dùng chung
write_queue = queue.Queue()
STATE_FILE = "tool_state.json"
helper = Helper()
class SimpleTool:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1000x800")
        self.root.title("🧰 Hieu Nguyen Tool")
        
        self.items = []
        self.items1 = []
        self.items2 = []
        self.items3 = []
        self.items4 = []
        self.items5 = []
        self.done = []
        self.running = False
        self.thread = None
        self.done_count = 0
        self.file_path = ""
        self.text_command_load = ""
        self.is_continue =True
        # ===== Layout =====
        self.left_frame = tk.LabelFrame(root, text="📄 Danh sách cần xử lý", padx=10, pady=10)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.right_frame = tk.LabelFrame(root, text="✅ Đã xử lý", padx=10, pady=10)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        # ===== Dòng lệnh Gologin =====
        self.command_frame = tk.LabelFrame(self.left_frame, text="💻 Dòng lệnh Gologin đầy đủ", padx=10, pady=10)
        self.command_frame.pack(fill=tk.X, pady=(10, 0))

        self.text_command = tk.Text(self.command_frame, height=10, width=80, font=("Arial", 8))
        self.text_command.pack()

        # ===== Bên trái =====
        btn_frame = tk.Frame(self.left_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Button(btn_frame, text="📂 Chọn File XML", command=self.load_file).pack(side=tk.LEFT, padx=(0, 5))

        self.script_type = tk.StringVar()
        self.script_type.set("OR CRAWL MULTI")  # mặc định
        script_options = ["RI CRAWL", "OR CRAWL", "OR CRAWL MULTI"]  # danh sách script hỗ trợ
        tk.OptionMenu(btn_frame, self.script_type, *script_options).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="Chạy", command=self.start_thread).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="Dừng", command=self.pause).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="💾 Lưu", command=self.save_state).pack(side=tk.LEFT)

        self.label_input_count = tk.Label(self.left_frame, text="Tổng: 0")
        self.label_input_count.pack()
        self.listbox_input = tk.Listbox(self.left_frame, width=60, height=30)
        self.listbox_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        input_scroll = tk.Scrollbar(self.left_frame, command=self.listbox_input.yview)
        input_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox_input.config(yscrollcommand=input_scroll.set)

        # ===== Bên phải =====

        self.label_done_count = tk.Label(self.right_frame, text="Đã xử lý: 0/0")
        self.label_done_count.pack()
        self.listbox_done = tk.Listbox(self.right_frame, width=60, height=30)
        self.listbox_done.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        done_scroll = tk.Scrollbar(self.right_frame, command=self.listbox_done.yview)
        done_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox_done.config(yscrollcommand=done_scroll.set)

        # Gắn sự kiện tắt cửa sổ
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Load trạng thái nếu có
        self.load_state()

    def on_close(self):
        # Gọi hàm kill chrome ở đây
        self.kill_chrome()
        self.root.destroy()  # Đóng cửa sổ

    def kill_chrome(self):
        # Kill tất cả các tiến trình Chrome và Chromedriver
        try:
            # Với Windows:
            subprocess.call('taskkill /F /IM chrome.exe /T', shell=True)
            subprocess.call('taskkill /F /IM chromedriver.exe /T', shell=True)
        except Exception as e:
            print("Lỗi khi kill chrome:", e)
    def launch_browser(self):
        cmd = self.text_command.get("1.0", tk.END).strip()

        if not cmd:
            messagebox.showwarning("Thiếu lệnh", "Vui lòng nhập dòng lệnh để chạy.")
            return

        try:
            subprocess.Popen(cmd, shell=True)
            print("🧪 Đã chạy dòng lệnh trình duyệt.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể chạy trình duyệt:\n{e}")


    def load_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml")])

        if not self.file_path:
            return
        file_path_contents = self.file_path.replace(".xml", "_contents.txt")
        open(file_path_contents, 'w').close()
        # Reset toàn bộ trạng thái
        self.pause()
        self.items = []
        self.items1 = []
        self.items2 = []
        self.items3 = []
        self.items4 = []
        self.items5 = []
        self.done = []
        self.done_count = 0
        self.root_id = None
        self.is_continue = False
        self.text_command_load = ""
        self.listbox_input.delete(0, tk.END)
        self.listbox_done.delete(0, tk.END)
        self.text_command.delete("1.0", tk.END)
        # Đọc file XML
        tree = ET.parse(self.file_path)
        root = tree.getroot()

        ns = {'ns': 'http://risk.regn.net/LeadList'}
        # Lấy Root ID
        self.root_id = root.attrib.get("ID")
        leads = root.findall('.//ns:Lead', ns)

        for lead in leads:
            case_key = lead.attrib.get("CaseKey")
            lead_id = lead.attrib.get("ID")
            if case_key and lead_id:
                self.items.append(f"{case_key} | {lead_id}")
            #print(self.items)
        for item in self.items:
            self.listbox_input.insert(tk.END, item)
        helper.split_items(self.items, n=5)
        self.items1 = helper.item1
        self.items2 = helper.item2
        self.items3 = helper.item3
        self.items4 = helper.item4
        self.items5 = helper.item5
        self.label_input_count.config(text=f"Tổng: {len(self.items)}")
        self.label_done_count.config(text=f"Đã xử lý: 0 / {len(self.items)}")
        self.del_state()

    def update_listboxes(self):
        self.label_input_count.config(text=f"Tổng: {len(self.items) + len(self.done)}")
        self.label_done_count.config(text=f"Đã xử lý: {self.done_count} / {len(self.items) + len(self.done)}")
        self.text_command.insert(tk.END, self.text_command_load)
        self.listbox_input.delete(0, tk.END)
        for item in self.items:
            self.listbox_input.insert(tk.END, item)

        self.listbox_done.delete(0, tk.END)
        for item in self.done:
            self.listbox_done.insert(tk.END, item)
    
    def start_thread(self):
        print(self.is_continue)
        if not self.file_path:
            messagebox.showerror("Lỗi", "Vui lòng nhập file!")
            return
        
        self.text_command_load=self.text_command.get("1.0", tk.END).strip()
        if self.text_command_load =="":
            print(self.text_command_load)
            messagebox.showerror("Lỗi", "Vui lòng nhập lệnh gologin!")
            return
        if not self.running:
            text = helper.ensure_remote_debugging_flags(self.text_command.get("1.0", tk.END).strip()) 
            try:
                subprocess.Popen(text, shell=True)
                print("Đã chạy lệnh.")
            except Exception as e:
                messagebox.showerror("Lỗi","Lỗi khi khởi động chorme")
                print(f"Lỗi khi chạy lệnh: {e}")
            self.running = True
            script_type = self.script_type.get()
            if script_type == "RI CRAWL":
                target_func = self.run_items_ri
            elif script_type == "OR CRAWL":
                target_func = self.run_items_or
            elif script_type == "OR CRAWL MULTI":
                target_func = self.run_items_or_multi
            else:
                messagebox.showerror("Lỗi", f"Không hỗ trợ script: {script_type}")
                return

            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(target=target_func, daemon=True)
                self.thread.start()


    def pause(self):
        self.running = False
        self.kill_chrome()
    def run_items_ri(self):
        script = ScriptRI()
        script.connect()
        time.sleep(3)
        success = script.first_run(self.root_id, self.file_path)
        while self.items and self.running and success:
            item = self.items.pop(0)
            if self.listbox_input.size() > 0:
                self.listbox_input.delete(0)
            
            if script.run(item, self.root_id,self.file_path):
                if script.click_on_case_link():
                    print(f"✅ Đã xử lý: {item}")
                    self.done.append(item)
                    self.done_count += 1
                    self.listbox_done.insert(tk.END, item)

                    self.label_done_count.config(
                        text=f"Đã xử lý: {self.done_count} / {len(self.items)}"
                    )
                    self.label_input_count.config(text=f"Tổng: {len(self.items)}")
                    script.clear_cookie()
                    self.save_state()
                else:
                    print(f"[❌] Lỗi khi xử lý: {item}")
            else:
                print(f"[❌] Lỗi khi xử lý: {item}")

    def run_items_or(self):
        script_or = ScriptOR()
        try:
            script_or.connect()
        except:
            messagebox.showerror("Lỗi", "Kết nối đến chrome vui lòng tắt chorme bấm tạm dừng rồi chạy lại!")
            return
        print(self.is_continue)
        if self.is_continue != True:
            print("self.is_continue")
            success,mess = script_or.first_run(self.root_id, self.file_path)
            if success == False:
                messagebox.showerror("Lỗi", mess)
                return
            self.is_continue =True
        
            
        while self.items and self.running:
            item = self.items[0]
            
            if script_or.run(item,self.file_path):
                    print(f"✅ Đã xử lý: {item}")
                    self.done.append(item)
                    self.done_count += 1
                    self.listbox_done.insert(tk.END, item)

                    self.label_done_count.config(
                        text=f"Đã xử lý: {self.done_count} / {len(self.items)}"
                    )
                    self.label_input_count.config(text=f"Tổng: {len(self.items)}")
                    del self.items[0]
                    if self.listbox_input.size() > 0:
                        self.listbox_input.delete(0)
                    self.save_state()   
                       
            else:
                print(f"[❌] Lỗi khi xử lý: {item}")
                #self.save_state()  
                return
    def handle_profile(self,index, items):
        print(f"🧑‍💻 Xử lý profile {index} với {len(items)} item(s)")

        scripor_multi = ScriptOR_multi(r"C:\Users\hieunk\Documents\hieunk-project\cdp_gologin\Profile {index}")
        if self.is_continue != True:
            print("self.is_continue")
            success,mess = scripor_multi.first_run(self.root_id, self.file_path)
            if success == False:
                messagebox.showerror("Lỗi", mess)
                return
            self.is_continue =True
        while item and self.running:
            item = items[0]
            res, data =scripor_multi.run(item)
            if res:
                    write_queue.put(data)
                    print(f"✅ Đã xử lý: {item}")
                    self.done.append(item)
                    self.done_count += 1
                    self.listbox_done.insert(tk.END, item)

                    self.label_done_count.config(
                        text=f"Đã xử lý: {self.done_count} / {len(items)}"
                    )
                    self.label_input_count.config(text=f"Tổng: {len(items)}")
                    del items[0]
                    if self.listbox_input.size() > 0:
                        self.listbox_input.delete(0)
                    self.save_state()   
                       
            else:
                print(f"[❌] Lỗi khi xử lý: {item}")
                #self.save_state()  
                return
    def writer_thread_func(self):
        output = self.file_path.replace(".xml", "_contents.txt")
        with open(output, "a", encoding="utf-8") as f:
            while True:
                item = write_queue.get()
                if item is None:
                    break
                f.write(item)
                f.flush()
    def run_items_or_multi(self):
        # 3️⃣ Khởi động writer thread
        writer_thread = threading.Thread(target=self.writer_thread_func)
        writer_thread.start()

        # 4️⃣ Khởi động nhiều thread crawl
        threads = []
        items_all = [self.items1, self.items2, self.items3, self.items4, self.items5]
        for i, item in enumerate(items_all):
            t = threading.Thread(target=self.handle_profile, args=(i, item))
            t.start()
            threads.append(t)

        # 5️⃣ Đợi tất cả crawl xong
        for t in threads:
            t.join()

        # 6️⃣ Kết thúc thread ghi
        write_queue.put(None)
        writer_thread.join()
        
    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "items": self.items,
                "items1": self.items1,
                "items2": self.items2,
                "items3": self.items3,
                "items4": self.items4,
                "items5": self.items5,
                "done": self.done,
                "count_done": self.done_count,
                "file_path": self.file_path,
                "root_id": self.root_id,
                "text_command_load": self.text_command.get("1.0", tk.END).strip()
            }, f, ensure_ascii=False, indent=2)

    def del_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "items": [],
                "items1": [],
                "items2": [],
                "items3": [],
                "items4": [],
                "items5": [],
                "done": [], 
                "count_done": 0, 
                "file_path": "", 
                "root_id": "",
                "text_command_load":""
                }, f, ensure_ascii=False, indent=2)

    def load_state(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.items = data.get("items", [])
                self.items1 = data.get("items1", [])
                self.items2 = data.get("items2", [])
                self.items3 = data.get("items3", [])
                self.items4 = data.get("items4", [])
                self.items5 = data.get("items5", [])
                self.done = data.get("done", [])
                self.root_id=data.get("root_id","")
                self.file_path = data.get("file_path","")
                self.done_count = data.get("count_done", 0)
                self.text_command_load=data.get("text_command_load","")
                
                self.update_listboxes()

# ===== Khởi chạy =====
if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleTool(root)
    root.mainloop()
