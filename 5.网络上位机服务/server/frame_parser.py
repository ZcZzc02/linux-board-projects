"""
frame_parser.py — LoRa 数据帧解析
支持：AD7606 (TYPE=0x01) / CAN (TYPE=0x02) / RS485 (TYPE=0x03)
注：LORA_TYPE_AD7606=0x01, LORA_TYPE_CAN=0x02, LORA_TYPE_RS485=0x03（与 F767 lora.h 一致）
"""
import struct
import crcmod

# CRC16/Modbus：多项式 0x8005，初始值 0xFFFF，输入输出均位反转
_crc16 = crcmod.predefined.mkCrcFun("modbus")


def calc_crc16(data: bytes) -> int:
    return _crc16(data)


def parse_frame(data: bytes) -> dict | None:
    """
    解析完整 LoRa 帧，返回解析结果字典，CRC 错误或帧格式错误返回 None。
    返回字典包含：
      node_addr, frame_type, raw_hex, error(可选), channels(AD7606), ...
    """
    if len(data) < 5:
        return None

    node_addr = data[0]
    frame_type = data[1]
    length = data[2]

    if len(data) != 3 + length + 2:
        return None  # 帧长度不符

    payload = data[3: 3 + length]
    crc_recv = (data[-2] << 8) | data[-1]
    crc_calc = calc_crc16(data[:-2])

    base = {
        "node_addr": node_addr,
        "frame_type": frame_type,
        "raw_hex": data.hex().upper(),
        "crc_ok": crc_recv == crc_calc,
    }

    if not base["crc_ok"]:
        base["error"] = f"CRC错误: 收到={crc_recv:04X} 计算={crc_calc:04X}"
        return base

    if frame_type == 0x01:
        return {**base, **_parse_ad7606(payload)}
    elif frame_type == 0x02:
        return {**base, "type_name": "CAN", "payload_hex": payload.hex().upper()}
    elif frame_type == 0x03:
        return {**base, **_parse_rs485(payload)}
    else:
        return {**base, "type_name": "UNKNOWN", "payload_hex": payload.hex().upper()}


def _parse_rs485(payload: bytes) -> dict:
    """parse RS485 measurement payload: 4 × uint16 寄存器（大端uint16）
    [voltage][current][soc][raw3] 各 2 字节，共 8 字节
    """
    base = {
        "type_name": "RS485",
        "payload_hex": payload.hex().upper(),
    }
    if len(payload) < 8:
        return base
    voltage = struct.unpack_from(">H", payload, 0)[0]
    current = struct.unpack_from(">H", payload, 2)[0]
    soc     = struct.unpack_from(">H", payload, 4)[0]
    raw3    = struct.unpack_from(">H", payload, 6)[0]
    return {**base, "voltage": voltage, "current": current, "soc": soc, "raw3": raw3}


def _parse_ad7606(payload: bytes) -> dict:
    """解析 AD7606 的 16 字节 PAYLOAD（8通道 × 2字节大端有符号 int16）"""
    if len(payload) < 16:
        return {"type_name": "AD7606", "error": "PAYLOAD长度不足"}

    channels = []
    for i in range(8):
        raw = struct.unpack_from(">h", payload, i * 2)[0]  # big-endian int16
        volt_mv = raw * 5000.0 / 32767.0
        channels.append(round(volt_mv, 2))

    return {
        "type_name": "AD7606",
        "channels_mv": channels,   # 单位 mV，列表索引即通道号
        "ch0_mv": channels[0],
        "ch1_mv": channels[1],
    }
