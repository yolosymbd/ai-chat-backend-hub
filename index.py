from main import app
from mangum import Mangum

# 把FastAPI应用包装成云函数可识别的handler
handler = Mangum(app)
