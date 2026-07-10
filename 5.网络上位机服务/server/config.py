# ============================================================
# 配置文件 — 修改这里切换 Broker
# ============================================================

# MQTT Broker 配置
# HiveMQ 公共测试 Broker（明文TCP，无需TLS，无需认证）
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_USE_TLS = False
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

# 为避免和其他人的 topic 冲突，使用唯一前缀
# 正式接入网关后，网关固件也要配置相同前缀
MQTT_TOPIC_PREFIX = "fengyan_daq_2026"

# 订阅所有节点的所有上行数据
MQTT_SUBSCRIBE_TOPICS = [
    f"{MQTT_TOPIC_PREFIX}/data/node/+/ad7606",
    f"{MQTT_TOPIC_PREFIX}/data/node/+/rs485",
    f"{MQTT_TOPIC_PREFIX}/data/node/+/can",
    f"{MQTT_TOPIC_PREFIX}/data/node/+/raw",
    f"{MQTT_TOPIC_PREFIX}/status/node/+",
    f"{MQTT_TOPIC_PREFIX}/status/gw",       # 网关连接状态
]

# 指令下发 topic 模板（使用时格式化 node_id）
MQTT_CMD_TOPIC = f"{MQTT_TOPIC_PREFIX}/cmd/node/{{node_id}}"

# 数据库
DATABASE_URL = "sqlite+aiosqlite:///./daq_data.db"

# Web 服务
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
