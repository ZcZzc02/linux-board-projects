# k7-gateway

K7 Linux 网关工程，用于逐步复现旧 STM32 网关功能：

- LoRa E22 与节点板通信
- LoRa 帧解析
- MQTT 数据上报
- 4G/5G 网络状态检查

当前第一阶段只实现可验证的基础工具和协议解析，不自动改设备树、不刷机、不控制模块电源。

## 已知硬件基线

根据交接文档，当前 K7 已确认：

- `/dev/ttyS3` 存在
- UART3 已启用
- I2C7 已关闭
- K7 UART3 本地回环通过
- E22-400T22D 可返回配置响应

## 快速检查

在 K7 上执行：

```bash
python3 -m k7_gateway self-check
```

读取 E22 配置：

```bash
python3 -m k7_gateway e22-read-config --device /dev/ttyS3
```

期望看到：

```text
RX_HEX=c100090000006500170b0000
```

监听 LoRa 原始帧：

```bash
python3 -m k7_gateway listen-lora --device /dev/ttyS3 --seconds 60
```

长期运行 LoRa 接收并写入 JSONL 日志：

```bash
python3 -m k7_gateway run-lora --device /dev/ttyS3 --log /var/log/k7-gateway/lora.jsonl
```

限时验证 30 秒，同时保存原始十六进制数据：

```bash
python3 -m k7_gateway run-lora --device /dev/ttyS3 --seconds 30 --raw-log /var/log/k7-gateway/lora.raw.log
```

联网后发布到 HiveMQ，让上位机后台接收：

```bash
python3 -m k7_gateway run-lora \
  --device /dev/ttyS3 \
  --log /var/log/k7-gateway/lora.jsonl \
  --mqtt-broker broker.emqx.io \
  --transport auto
```

`--transport auto` 会根据当前默认路由自动上报网关链路状态：

- 默认路由走 `wlan*`：上报 `wifi`
- 默认路由走 RG200U 暴露的 USB/NCM 网卡：通过 `AT+COPS?` 判断并上报 `4g` 或 `5g`
- 网络暂时不可用：继续收 LoRa、写本地 JSONL 日志，并周期重试 MQTT

实际“优先 5G/4G，WiFi 兜底”的路由选择由 Linux / NetworkManager 负责。推荐把蜂窝连接 route metric 设为 `100`，WiFi route metric 设为 `600`。

检查当前出口：

```bash
ip route
PYTHONPATH=/root/k7-gateway/src python3 - <<'PY'
from k7_gateway.network_status import default_route_interface, resolve_transport
print(default_route_interface())
print(resolve_transport("auto"))
PY
```

离线解析十六进制帧：

```bash
python3 -m k7_gateway parse-hex 01011000010002000300040005000600070008xxxx
```

其中末尾 `xxxx` 需要替换成真实 CRC。

## 本机测试

在开发电脑上执行：

```bash
python -m unittest discover -s 2.1.Linux网关/k7-gateway/tests
```

## 后续路线

1. 在 K7 上跑通 `self-check`。
2. 在配置模式下复核 `e22-read-config`。
3. 切到 E22 透明传输模式，跑 `listen-lora`。
4. 用节点板真实数据补充解析测试。
5. 接入 MQTT 上报。
6. 接入 4G/5G/WiFi 自动链路状态上报和 systemd 服务。
