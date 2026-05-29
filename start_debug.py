import sys
import traceback

try:
    print("正在导入app模块...")
    import app
    print("✓ 模块导入成功")
    
    print("正在启动服务器...")
    app.app.run(host='127.0.0.1', port=5050, debug=False)
    
except Exception as e:
    print("\n" + "="*60)
    print("❌ 启动失败！")
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {str(e)}")
    print("="*60)
    traceback.print_exc()
    input("\n按回车键退出...")
