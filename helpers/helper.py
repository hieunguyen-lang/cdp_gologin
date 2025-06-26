import re

class Helper:
    def ensure_remote_debugging_flags(self, command: str) -> str:
        command = command.strip()

        # Xóa flag --host-resolver-rules="..."
        command = re.sub(r'--host-resolver-rules="[^"]*"', '', command).strip()

        # Đảm bảo --remote-debugging-port=9222
        if "--remote-debugging-port=" in command:
            command = re.sub(r"--remote-debugging-port=\d+", "--remote-debugging-port=9222", command)
        elif "--remote-debugging-port" in command:
            command = command.replace("--remote-debugging-port", "--remote-debugging-port=9222")
        else:
            command += " --remote-debugging-port=9222"

        # Đảm bảo có --remote-allow-origins=*
        if "--remote-allow-origins=*" not in command:
            command += " --remote-allow-origins=*"

        return command
