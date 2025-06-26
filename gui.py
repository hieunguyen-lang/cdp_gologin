import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from scripts.script_ri import ScriptRI  
from scripts.script_or import ScriptOR  # Giả sử bạn có một script OR tương tự
from helpers.helper import Helper
STATE_FILE = "tool_state.json"
helper = Helper()
class SimpleTool:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1000x800")
        self.root.title("🧰 Hieu Nguyen Tool")
        
        self.items = []
        self.done = []
        self.running = False
        self.thread = None
        self.done_count = 0
        self.file_path = ""
        self.text_command_load = ""
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
        self.script_type.set("OR CRAWL")  # mặc định
        script_options = ["RI CRAWL", "OR CRAWL", "Other2"]  # danh sách script hỗ trợ
        tk.OptionMenu(btn_frame, self.script_type, *script_options).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="▶️ Chạy", command=self.start_thread).pack(side=tk.LEFT, padx=(0, 5))
        

        tk.Button(btn_frame, text="⏸ Tạm dừng", command=self.pause).pack(side=tk.LEFT, padx=(0, 5))

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

        # Load trạng thái nếu có
        self.load_state()
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
        self.done = []
        self.done_count = 0
        self.root_id = None
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
            else:
                messagebox.showerror("Lỗi", f"Không hỗ trợ script: {script_type}")
                return

            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(target=target_func, daemon=True)
                self.thread.start()


    def pause(self):
        self.running = False

    def run_items_ri(self):
        script = ScriptRI()
        script.connect()
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
                        text=f"Đã xử lý: {self.done_count} / {len(self.items) + len(self.done)}"
                    )
                    self.label_input_count.config(text=f"Tổng: {len(self.items) + len(self.done)}")
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
        success,mess = script_or.first_run(self.root_id, self.file_path)
        if success == False:
            messagebox.showerror("Lỗi", mess)
            return
        while self.items and self.running:
            item = self.items.pop(0)
            if self.listbox_input.size() > 0:
                self.listbox_input.delete(0)
            if script_or.run(item,self.file_path):
                    print(f"✅ Đã xử lý: {item}")
                    self.done.append(item)
                    self.done_count += 1
                    self.listbox_done.insert(tk.END, item)

                    self.label_done_count.config(
                        text=f"Đã xử lý: {self.done_count} / {len(self.items) + len(self.done)}"
                    )
                    self.label_input_count.config(text=f"Tổng: {len(self.items) + len(self.done)}")
                    self.save_state()
            else:
                print(f"[❌] Lỗi khi xử lý: {item}")


    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "items": self.items,
                "done": self.done,
                "count_done": self.done_count,
                "file_path": self.file_path,
                "root_id": self.root_id,
                "text_command_load": self.text_command.get("1.0", tk.END).strip()
            }, f, ensure_ascii=False, indent=2)

    def del_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"items": [], "done": [], "count_done": 0, "file_path": "", "root_id": "","text_command_load":""}, f, ensure_ascii=False, indent=2)

    def load_state(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.items = data.get("items", [])
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
