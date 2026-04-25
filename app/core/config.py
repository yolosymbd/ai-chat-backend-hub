# 所有模型配置、环境变量、常量、提示词全原封不动搬过来
import os
from dotenv import load_dotenv

load_dotenv()

# ===================== 全局常量 =====================
DB_PATH = "chat.db"
MIN_SEND_INTERVAL = 0.008

# ===================== 系统提示词（完全原样保留） =====================
SYSTEM_PROMPT_NORMAL = """
【严格回答约束·永久生效，一字不可违反】
1. 【仅本次对话被注入参考文档资料时】：100%依据资料回答，绝不幻觉，末尾必须标注引用来源。
2. 【无任何参考文档、纯日常普通闲聊问答时】：
   自由正常回答用户问题，**全程绝对禁止输出任何「来源、参考、片段、引用」相关所有文字、句子、后缀**！
   不允许凭空编造来源标注，不允许附加任何无关格式后缀。
3. 回答精简准确、逻辑通顺，不编造信息。
4. 无相关知识直接说明，不强行拓展内容。
"""

SYSTEM_PROMPT_TOOL = """
【绝对强制规则，一字不能违反】
1. 全程**只输出纯JSON字符串，无任何汉字、无任何前缀后缀、无markdown代码块、无换行、无空格、无解释、无备注**
2. 绝对不允许输出任何自然语言文字
3. 严格固定格式，仅能输出下方模板，无任何修改：
{"name":"工具名称","parameters":{"参数名":"参数值"}}

可用工具列表：
1. weather：天气查询，参数 city 城市名
2. calc：数学计算器，参数 exp 完整数学表达式
3. time：获取当前北京时间，无参数，parameters传空对象{}
4. search：网络搜索，参数 query 搜索词
"""

# ===================== 多模型配置（完全原版不动） =====================
MODEL_CONFIG = {
    "glm": {
        "name": "glm-4-flash",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key_env": "API_KEY"
    },
    "doubao": {
        "name": "doubao-seed-1-8-251228",
        "url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "key_env": "DOUBAO_API_KEY",
        "hard_key": "ark-6240f8e7-c6c9-474a-893c-281c39262031-8dce9"
    }
}