# K7 网关 Bring-up 步骤

本文档记录从当前 K7 状态继续开发时的最小验证顺序。

## 1. 不要先做的事

- 不要先重刷系统。
- 不要先改设备树。
- 不要先重插 E22 全部线。
- 不要先假设 SSH、GUI 或网络一定可用。

## 2. 串口控制台确认

优先用调试串口进入 K7 shell。官方资料中 K7 调试串口波特率为 `1500000`。

## 3. 系统基线自检

```bash
python3 -m k7_gateway self-check
```

重点看：

- `/dev/ttyS3`
- UART3 设备树状态
- I2C7 设备树状态
- `/dev/ttyUSB2`
- `/usr/bin/4G_dialing.sh`
- 默认路由

## 4. E22 配置读取

确认 E22 处于配置模式后执行：

```bash
python3 -m k7_gateway e22-read-config --device /dev/ttyS3
```

## 5. LoRa 透明接收

切到 E22 透明传输模式后执行：

```bash
python3 -m k7_gateway listen-lora --device /dev/ttyS3 --seconds 60
```

如果没有任何数据，先确认节点板是否在发送，再确认 E22 模式和接线。

## 6. 5G/4G

K7 资料中 4G/5G 模块通常通过 Mini-PCIe 接入，系统侧会检测 `/dev/ttyUSB2`，并使用 `/usr/bin/4G_dialing.sh` 或 `quectel-CM` 进行拨号。

第一阶段只检查这些系统入口是否存在，不在应用里直接复刻 STM32 的 AT 指令拨号状态机。
