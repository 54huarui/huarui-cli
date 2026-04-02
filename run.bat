@echo off
echo 正在激活虚拟环境并运行 app.py...

:: 激活虚拟环境
call .\.venv\Scripts\activate

:: 运行 app.py
python app.py

echo 程序已退出，按任意键关闭窗口...
pause