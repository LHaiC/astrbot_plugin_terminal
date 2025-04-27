from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import subprocess
import asyncio
import re
from datetime import datetime, timedelta
import os

@register("terminal", "LHaiC", "通过和AstrBot对话调用服务器终端", "v1.0.2")
class TerminalPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.active_sessions = {}
        self.session_prefix = "astrbot_terminal"
        self.session_timeout = timedelta(minutes=30)
        asyncio.create_task(self._cleanup_sessions())

    @filter.command_group("terminal")
    def terminal_group(self):
        """终端操作指令组"""
        pass
    
    @filter.permission_type(filter.PermissionType.ADMIN)
    @terminal_group.command("on")
    async def start_terminal(self, event: AstrMessageEvent):
        """启动终端会话"""
        user_id = event.get_sender_id()
        
        if user_id in self.active_sessions:
            yield event.plain_result("⚠️ 您已有活跃的终端会话")
            return

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        session_name = f"{self.session_prefix}_{user_id}_{timestamp}"
        
        try:
            subprocess.run([
                "tmux", "new-session", "-d", "-s", session_name,
                "-x", "80", "-y", "24", "/bin/bash"
            ], check=True)
            
            self.active_sessions[user_id] = {
                "session": session_name,
                "last_active": datetime.now()
            }
            
            yield event.plain_result(
                "🟢 终端会话已启动\n"
                "直接输入命令即可执行\n"
                "使用`/terminal off`关闭会话\n"
                "⚠️ 会话30分钟无操作自动关闭"
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"启动tmux失败: {str(e)}")
            yield event.plain_result("❌ 终端会话启动失败")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @terminal_group.command("off") 
    async def stop_terminal(self, event: AstrMessageEvent):
        """关闭终端会话"""
        user_id = event.get_sender_id()
        if user_id not in self.active_sessions:
            yield event.plain_result("⚠️ 没有活跃的终端会话")
            return
        
        session_name = self.active_sessions.pop(user_id)["session"]
        
        try:
            subprocess.run(["tmux", "kill-session", "-t", session_name], check=True)
            yield event.plain_result("🔴 终端会话已关闭")
        except subprocess.CalledProcessError as e:
            logger.error(f"关闭tmux失败: {str(e)}")
            yield event.plain_result("❌ 终端会话关闭失败")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.regex(r"^(?!terminal\s+(on|off)).+")
    async def execute_command(self, event: AstrMessageEvent):
        """执行终端命令（文件重定向版）"""
        user_id = event.get_sender_id()
        if user_id not in self.active_sessions:
            return
        
        command = event.message_str.strip()
        session_name = self.active_sessions[user_id]["session"]
        
        if not self._is_command_safe(command):
            yield event.plain_result("⛔ 拒绝执行潜在危险命令")
            return
        
        try:
            self.active_sessions[user_id]["last_active"] = datetime.now()
            
            # 1. 创建唯一的临时文件名
            temp_id = os.urandom(4).hex()
            tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")

            # 确保tmp目录存在
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir, exist_ok=True)

            output_file = os.path.join(tmp_dir, f"astrbot_term_out_{temp_id}")
            exit_code_file = os.path.join(tmp_dir, f"astrbot_term_exit_{temp_id}")
            pwd_file = os.path.join(tmp_dir, f"astrbot_term_pwd_{temp_id}")
            
            # 2. 清屏并执行命令，将输出重定向到临时文件，同时获取当前目录
            subprocess.run([
                "tmux", "send-keys", "-t", session_name,
                f"clear && {{ {command}; }} > {output_file} 2>&1; echo $? > {exit_code_file}; pwd > {pwd_file}", "Enter"
            ], check=True)
            
            # 3. 等待命令执行完成
            await asyncio.sleep(1.5)  # 给命令足够的执行时间
            
            # 4. 读取命令输出、退出状态和当前目录
            output = ""
            exit_code = -1
            current_dir = ""
            
            try:
                # 读取输出
                if os.path.exists(output_file):
                    with open(output_file, "r", encoding="utf-8") as f:
                        output = f.read().rstrip()
                        
                # 读取退出码    
                if os.path.exists(exit_code_file):
                    with open(exit_code_file, "r") as f:
                        exit_code_str = f.read().strip()
                        if exit_code_str.isdigit():
                            exit_code = int(exit_code_str)
                
                # 读取当前目录
                if os.path.exists(pwd_file):
                    with open(pwd_file, "r") as f:
                        current_dir = f.read().strip()
                            
                # 清理临时文件
                for file in [output_file, exit_code_file, pwd_file]:
                    if os.path.exists(file):
                        os.remove(file)
                        
            except Exception as e:
                logger.error(f"读取命令输出失败: {str(e)}")
            
            # 5. 返回结果
            result_text = ""
            if output.strip():
                result_text = f"📋 命令输出：\n{output}"
            else:
                result_text = "📋 命令已执行，无输出"
                
            # 添加退出码信息（如果不为0）
            if exit_code != 0 and exit_code != -1:
                result_text += f"\n⚠️ 命令退出码: {exit_code}"
            
            # 添加当前目录信息
            if current_dir:
                result_text += f"\n📂 当前目录: {current_dir}"
                
            yield event.plain_result(result_text)
            
        except Exception as e:
            logger.error(f"执行命令失败: {str(e)}")
            yield event.plain_result(f"❌ 命令执行错误: {str(e)}")

    def _is_command_safe(self, command: str) -> bool:
        """命令安全检查"""
        blocked = [
            r"rm\s+-[rf]", r"sudo", r"^\s*:?\s*\!",
            r"^\s*\&", r"^\s*\|\s*[&\|]", 
            r"^\s*>\s*\/", r"^\s*<\s*\/"
        ]
        return not any(re.search(p, command) for p in blocked)

    async def _cleanup_sessions(self):
        """定时清理超时会话"""
        while True:
            await asyncio.sleep(300)
            now = datetime.now()
            expired = [
                uid for uid, info in self.active_sessions.items()
                if now - info["last_active"] > self.session_timeout
            ]
            
            for user_id in expired:
                session = self.active_sessions.pop(user_id)["session"]
                subprocess.run(["tmux", "kill-session", "-t", session])
                logger.info(f"清理超时会话: {user_id} - {session}")

    async def terminate(self):
        """插件卸载时清理所有会话和临时文件"""
        for user_id in list(self.active_sessions.keys()):
            session = self.active_sessions.pop(user_id)["session"]
            subprocess.run(["tmux", "kill-session", "-t", session], stderr=subprocess.DEVNULL)

        tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
        if os.path.exists(tmp_dir) and os.path.isdir(tmp_dir):
            for filename in os.listdir(tmp_dir):
                file_path = os.path.join(tmp_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            logger.info("已清空临时文件夹")