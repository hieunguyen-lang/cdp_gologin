import re

class Helper:
    def ensure_remote_debugging_flags(self, command: str, port: int = 9222, extension_path: str = r'D:\casecrawl\my_extenstion') -> str:
        command = command.strip()

        # Xóa flag --host-resolver-rules="..."
        command = re.sub(r'--host-resolver-rules="[^"]*"', '', command).strip()

        # Kiểm tra hoặc cập nhật --remote-debugging-port
        if re.search(r"--remote-debugging-port=\d+", command):
            command = re.sub(r"--remote-debugging-port=\d+", f"--remote-debugging-port={port}", command)
        elif "--remote-debugging-port" in command:
            command = command.replace("--remote-debugging-port", f"--remote-debugging-port={port}")
        else:
            command += f" --remote-debugging-port={port}"

        # Đảm bảo có --remote-allow-origins=*
        if "--remote-allow-origins=*" not in command:
            command += " --remote-allow-origins=*"

        # Đảm bảo có --load-extension (nếu chưa)
        # if "--load-extension" not in command and extension_path:
        #     command += f' --load-extension="{extension_path}"'
        
        return command
