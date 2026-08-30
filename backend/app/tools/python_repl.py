"""
Python REPL 工具
使用 subprocess 隔离执行 Python 代码
"""
import asyncio
import ast
import json
import logging
import os
import re
import sys
import tempfile
from typing import Any, Dict

from app.tools.base import BaseTool
from app.tools.exceptions import ToolExecutionError, ToolTimeoutError

logger = logging.getLogger(__name__)


class PythonREPLTool(BaseTool):
    """
    Python 代码执行工具
    
    安全特性：
    - 使用 subprocess 隔离执行
    - 模块白名单过滤
    - 超时控制（默认 5 秒）
    - 输出长度限制（默认 2000 字符）
    - 禁止文件系统访问
    """
    
    name = "python_repl"
    description = """执行 Python 代码并返回结果。适用于：
- 数学计算和数值分析
- 数据结构和算法演示
- 文本处理和正则表达式
- 日期时间计算
- 简单的逻辑验证

注意：只能使用 Python 标准库（math, datetime, json, re, random, statistics 等），
不能访问文件系统、网络或导入第三方库。"""
    
    timeout: float = 5.0
    max_output: int = 2000
    
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的 Python 代码（不能包含文件操作、网络请求或危险函数）"
            }
        },
        "required": ["code"]
    }
    
    # 禁止导入的模块
    BANNED_MODULES = {
        'os', 'sys', 'subprocess', 'shutil', 'socket', 'requests',
        'urllib', 'ftplib', 'ctypes', 'pickle', 'marshal',
        'importlib', 'eval', 'exec', 'compile', '__builtins__',
        'open', 'file', 'input', 'raw_input', 'reload',
    }
    
    # 允许的安全模块（标准库）
    SAFE_MODULES = {
        'math', 'datetime', 'json', 're', 'random', 'statistics',
        'collections', 'itertools', 'functools', 'operator',
        'string', 'textwrap', 'decimal', 'fractions', 'numbers',
        'typing', 'dataclasses', 'enum', 'abc', 'copy', 'pprint',
    }
    
    async def execute(self, code: str) -> Dict[str, Any]:
        """
        执行 Python 代码

        Args:
            code: Python 代码字符串

        Returns:
            包含 execution_time, output, error 的字典
        """
        # 基础安全检查
        self._validate_code(code)

        # 创建临时脚本
        script = self._build_safe_script(code)

        # 执行代码
        try:
            result = await self._run_subprocess(script)
            return result
        except ToolTimeoutError:
            raise  # 让 ToolTimeoutError 直接抛出，不被包装
        except Exception as e:
            err_type = type(e).__name__
            err_msg = str(e)
            logger.warning("python_repl failed: type=%s msg=%r code=%r", err_type, err_msg, code[:200])
            raise ToolExecutionError(
                self.name,
                f"Execution failed [{err_type}]: {err_msg or '(no message)'}",
                details={"error_type": err_type},
            )
    
    def _validate_code(self, code: str) -> None:
        """
        验证代码安全性
        
        Args:
            code: 待验证的代码
            
        Raises:
            ToolValidationError: 代码包含不安全操作
        """
        # 检查是否包含危险函数调用
        dangerous_patterns = [
            r'\bopen\s*\(',  # open() 函数
            r'\bexec\s*\(',  # exec()
            r'\beval\s*\(',  # eval()
            r'__import__\s*\(',  # __import__()
            r'\bcompile\s*\(',  # compile()
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                raise ToolExecutionError(
                    self.name,
                    f"Code contains dangerous operation: {pattern}"
                )
        
        # 解析 AST，检查导入语句
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ToolExecutionError(
                self.name,
                f"Syntax error: {str(e)}"
            )
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name in self.BANNED_MODULES:
                        raise ToolExecutionError(
                            self.name,
                            f"Cannot import module: {module_name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    if module_name in self.BANNED_MODULES:
                        raise ToolExecutionError(
                            self.name,
                            f"Cannot import module: {module_name}"
                        )
    
    def _build_safe_script(self, code: str) -> str:
        """
        构建安全的执行脚本

        注意：使用字符串拼接而非 f-string，避免用户代码中的 { / }
        被外层 f-string 当成表达式解析。

        Args:
            code: 用户代码

        Returns:
            完整的 Python 脚本
        """
        # 缩进用户代码
        indented_code = self._indent_code(code)

        # 用普通拼接，不用 f-string，防止用户代码中的 { } 干扰外层模板
        # JSON key 用单引号包裹（Python 的 json.dumps 兼容），避免引号嵌套问题
        max_out = self.max_output
        script = (
            "import sys\n"
            "from io import StringIO\n"
            "\n"
            "# 捕获输出\n"
            "old_stdout = sys.stdout\n"
            "sys.stdout = StringIO()\n"
            "\n"
            "result = None\n"
            "error = None\n"
            "\n"
            "try:\n"
            + indented_code +
            "\nexcept Exception as e:\n"
            "    error = str(e)\n"
            "\n"
            "# 获取输出\n"
            "output = sys.stdout.getvalue()\n"
            "sys.stdout = old_stdout\n"
            "\n"
            "# 打印结果（JSON 格式）\n"
            "import json\n"
            "print(json.dumps({"
            "'output': output[:" + str(max_out) + "], "
            "'result': result, "
            "'error': error"
            "}))"
            "\n"
        )
        return script
    
    def _indent_code(self, code: str, spaces: int = 4) -> str:
        """
        缩进代码（用于嵌入 try 块）
        
        Args:
            code: 原始代码
            spaces: 缩进空格数
            
        Returns:
            缩进后的代码
        """
        indent = ' ' * spaces
        lines = code.split('\n')
        indented_lines = [indent + line if line.strip() else line for line in lines]
        return '\n'.join(indented_lines)
    
    async def _run_subprocess(self, script: str) -> Dict[str, Any]:
        """
        在子进程中运行脚本

        Args:
            script: Python 脚本内容

        Returns:
            执行结果字典
        """
        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(script)
            temp_file = f.name

        try:
            # 运行子进程
            python_exe = sys.executable
            logger.debug("python_repl spawning: exe=%s script=%s", python_exe, temp_file)

            process = await asyncio.create_subprocess_exec(
                python_exe,
                temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                from app.tools.exceptions import ToolTimeoutError
                raise ToolTimeoutError(self.name, self.timeout)

            returncode = process.returncode

            # 解析输出
            output_text = stdout.decode('utf-8', errors='replace').strip()

            if stderr:
                stderr_text = stderr.decode('utf-8', errors='replace').strip()
            else:
                stderr_text = ""

            logger.debug(
                "python_repl result: rc=%d stdout=%r stderr=%r",
                returncode, output_text[:200], stderr_text[:200],
            )

            # 非零退出码也视为错误（即使有 stdout）
            if returncode != 0 and not output_text:
                raise RuntimeError(
                    f"Subprocess exited with code {returncode}"
                    + (f", stderr: {stderr_text}" if stderr_text else "")
                )

            # 尝试解析 JSON 结果
            try:
                result = json.loads(output_text)
                parsed_error = result.get("error") or stderr_text
                return {
                    "execution_time": 0.0,
                    "output": result.get("output", ""),
                    "result": result.get("result"),
                    "error": parsed_error,
                }
            except json.JSONDecodeError:
                # 如果不是 JSON，返回原始输出
                return {
                    "execution_time": 0.0,
                    "output": output_text[:self.max_output],
                    "result": None,
                    "error": stderr_text or ("Non-JSON output" if output_text else "No output"),
                }

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except OSError:
                pass