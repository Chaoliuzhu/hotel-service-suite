---
name: hotel-luggage-storage
description: 酒店行李寄存全流程管理——寄存登记、条码打印、电子凭证发送、取件核销、超期预警。支持热敏标签打印机、飞书卡片/短信/微信三渠道电子凭证。
触发词：寄存行李、行李寄存、寄存登记、取行李、行李领取、行李条码、行李标签、行李牌、寄存凭证、行李超期、行李查询、行李台账
version: 2.0.0
---

# 酒店行李寄存管理系统

## 核心能力概述

本技能实现酒店行李寄存的全生命周期管理，覆盖从宾客办理寄存到取件核销的完整链路：

1. **寄存登记**：采集宾客信息、行李信息，生成唯一寄存单号，写入飞书多维表格
2. **条码标签打印**：通过 TSPL 指令驱动热敏标签打印机，输出含条码的行李标签
3. **电子凭证发送**：支持飞书交互卡片、短信、微信三渠道发送寄存凭证
4. **取件核销**：验证码 + 寄存单号双重校验，自动更新取件状态
5. **超期预警**：24h / 48h / 72h 三级预警机制，自动推送提醒
6. **台账查询**：按日期、状态、房号、宾客姓名等多维度查询行李台账

---

## 数据底座

本系统的数据存储使用飞书多维表格（Bitable）：

| 参数 | 值 |
|------|-----|
| `app_token` | `Atj6bOVJtaDGSjspKDqcx3Jqnfd` |
| `table_id` | `tblMPvX3VKodb80I` |

所有读写操作通过 `lark-cli base` 命令完成。

---

## 字段完整映射

以下为多维表格中全部 19 个字段及其在系统中的映射关系：

| 序号 | 字段名（多维表格） | 字段类型 | 枚举值 / 说明 | 系统变量映射 |
|------|---------------------|----------|----------------|--------------|
| 1 | 寄存单号 | 文本 | 格式：`LG-YYYYMMDD-XXX`，如 `LG-20260623-001` | `deposit_number` |
| 2 | 宾客姓名 | 文本 | 宾客全名 | `guest_name` |
| 3 | 房号 | 文本 | 当前入住房号或历史房号 | `room_number` |
| 4 | 入住房号 | 文本 | 入住时的房号（可能与当前房号不同） | `checkin_room` |
| 5 | 联系方式 | 文本 | 手机号码（11 位） | `phone` |
| 6 | 寄存日期 | 日期 | ISO 8601 格式：`2026-06-23T14:30:00+08:00` | `deposit_datetime` |
| 7 | 寄存件数 | 数字 | 整数，默认 1 | `item_count` |
| 8 | 寄存类型 | 单选 | `普通行李` / `贵重行李` / `大件箱包` / `易碎物品` | `deposit_type` |
| 9 | 寄存位置 | 单选 | `一楼行李房` / `三楼长住行李房` | `storage_location` |
| 10 | 行李描述 | 文本 | 行李外观描述，如"黑色28寸行李箱1个，红色手提袋1个" | `description` |
| 11 | 标签打印状态 | 单选 | `未打印` / `已打印` / `已补打` | `label_status` |
| 12 | 取件验证码 | 文本 | 4-6 位数字随机码，如 `8826` | `pickup_code` |
| 13 | 取件日期 | 日期 | ISO 8601 格式 | `pickup_date` |
| 14 | 取件时间 | 文本 | 格式：`HH:mm`，如 `15:30` | `pickup_time` |
| 15 | 状态 | 单选 | `待取` / `已取` | `status` |
| 16 | 经办人 | 文本 | 办理寄存的员工姓名 | `operator` |
| 17 | 取件经办人 | 文本 | 办理取件的员工姓名 | `pickup_operator` |
| 18 | 备注 | 文本 | 补充说明 | `remark` |
| 19 | （预留扩展字段） | — | — | — |

---

## 编号规则

寄存单号生成规则：`LG-YYYYMMDD-XXX`

- `LG`：Luggage 固定前缀
- `YYYYMMDD`：寄存日期（8 位）
- `XXX`：当日三位顺序号，从 `001` 开始递增

生成算法：
1. 查询多维表格中当日（`寄存日期` 在 `[今日 00:00:00, 今日 23:59:59]` 范围内）的全部记录
2. 取最大序号 + 1，左补零至 3 位
3. 若当日无记录，则序号为 `001`

```bash
# 查询当日寄存记录数
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"寄存日期","operator":"is","value":["TODAY"]}]}' \
  --fields '["寄存单号"]'
```

---

## 寄存操作流程

### 前置校验

在执行寄存操作前，必须确认以下信息已收集：

| 必填信息 | 对应字段 | 校验规则 |
|----------|----------|----------|
| 宾客姓名 | 宾客姓名 | 非空，2-20 个字符 |
| 房号 | 房号 | 非空 |
| 联系方式 | 联系方式 | 11 位手机号 |
| 寄存件数 | 寄存件数 | 正整数，>= 1 |
| 行李描述 | 行李描述 | 非空 |
| 寄存类型 | 寄存类型 | 必须在枚举值中 |
| 寄存位置 | 寄存位置 | 必须在枚举值中 |

### 操作步骤

**Step 1：生成寄存单号**

```bash
# 1. 查询当日已有记录数
TODAY_COUNT=$(lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"寄存日期","operator":"is","value":["TODAY"]}]}' \
  --fields '["寄存单号"]' \
  --format json | jq '.items | length')

# 2. 计算序号
SEQ=$(printf "%03d" $((TODAY_COUNT + 1)))

# 3. 拼接寄存单号
DEPOSIT_NUMBER="LG-$(date +%Y%m%d)-${SEQ}"
```

**Step 2：生成取件验证码**

```bash
# 生成 4 位随机数字验证码
PICKUP_CODE=$(printf "%04d" $((RANDOM % 10000)))
```

**Step 3：写入多维表格**

```bash
lark-cli base +record-create \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --fields '{
    "寄存单号": "LG-20260623-001",
    "宾客姓名": "张三",
    "房号": "1208",
    "入住房号": "1208",
    "联系方式": "13800138000",
    "寄存日期": "2026-06-23T14:30:00+08:00",
    "寄存件数": 2,
    "寄存类型": "普通行李",
    "寄存位置": "一楼行李房",
    "行李描述": "黑色28寸行李箱1个，红色手提袋1个",
    "标签打印状态": "未打印",
    "取件验证码": "8826",
    "状态": "待取",
    "经办人": "行李员小李"
  }'
```

**Step 4：打印条码标签**（详见"条码标签打印流程"）

**Step 5：发送电子凭证**（详见"电子凭证发送流程"）

---

## 取件核销流程

### 核销校验

取件时必须提供以下信息中的至少两项：
- 寄存单号（`寄存单号`）
- 取件验证码（`取件验证码`）
- 宾客姓名 + 房号（组合查询）

### 操作步骤

**Step 1：查询寄存记录**

```bash
# 按寄存单号查询
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"寄存单号","operator":"is","value":["LG-20260623-001"]},{"field_name":"状态","operator":"is","value":["待取"]}]}' \
  --format json
```

**Step 2：验证码校验**

```
比对用户提供的验证码与记录中的「取件验证码」字段：
- 匹配 → 继续
- 不匹配 → 拒绝取件，提示"验证码错误，请核实后重试"
```

**Step 3：更新取件状态**

```bash
lark-cli base +record-update \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{
    "状态": "已取",
    "取件日期": "2026-06-24T10:15:00+08:00",
    "取件时间": "10:15",
    "取件经办人": "行李员小王"
  }'
```

**Step 4：确认取件完成**

向宾客确认行李已取出，并告知：
- "您的行李已取回，寄存单号 LG-20260623-001 已核销。"
- 如有需要可补打取件凭证。

---

## 条码标签打印流程

### 打印机要求

- 类型：热敏标签打印机（如 TSC TTP-244 Pro、佳博 GP-1324D）
- 标签尺寸：60mm x 40mm（推荐）或 50mm x 30mm
- 通信方式：TCP/IP（网口）或 USB
- 指令集：TSPL（TSCLIB）

### TSPL 打印指令

以下为完整的热敏标签打印指令，生成含 Code128 条码的行李标签：

```tspl
SIZE 60 mm, 40 mm
GAP 2 mm, 0 mm
DIRECTION 1
REFERENCE 0, 0
SET TEAR OFF
SET CUTTER OFF
CLS

! 酒店 Logo 区域（可选，使用预存位图）
! BITMAP 10, 5, 60, 20, 0, <bitmap_data>

! 标题
TEXT 200, 8, "TSS24.BF2", 0, 1, 1, "行李寄存标签"

! 寄存单号（大字）
TEXT 150, 40, "TSS24.BF2", 0, 1, 1, "LG-20260623-001"

! 条码（Code128）
BARCODE 200, 65, "128", 50, 1, 0, 2, 2, "LG-20260623-001"

! 宾客信息
TEXT 10, 130, "TSS24.BF2", 0, 1, 1, "宾客: 张三"
TEXT 10, 155, "TSS24.BF2", 0, 1, 1, "房号: 1208"
TEXT 10, 180, "TSS24.BF2", 0, 1, 1, "件数: 2"
TEXT 10, 205, "TSS24.BF2", 0, 1, 1, "类型: 普通行李"
TEXT 10, 230, "TSS24.BF2", 0, 1, 1, "位置: 一楼行李房"
TEXT 10, 255, "TSS24.BF2", 0, 1, 1, "日期: 2026-06-23"

! 分割线
BAR 10, 280, 460, 2

! 取件验证码（醒目大字）
TEXT 120, 290, "TSS24.BF2", 0, 1, 1, "取件验证码: 8826"

PRINT 1
```

### 网络打印命令

```bash
# 通过 TCP 发送 TSPL 指令到打印机
python3 -c "
import socket
tspl = '''SIZE 60 mm, 40 mm
GAP 2 mm, 0 mm
DIRECTION 1
REFERENCE 0, 0
CLS
TEXT 200, 8, \"TSS24.BF2\", 0, 1, 1, \"行李寄存标签\"
TEXT 150, 40, \"TSS24.BF2\", 0, 1, 1, \"${DEPOSIT_NUMBER}\"
BARCODE 200, 65, \"128\", 50, 1, 0, 2, 2, \"${DEPOSIT_NUMBER}\"
TEXT 10, 130, \"TSS24.BF2\", 0, 1, 1, \"宾客: ${GUEST_NAME}\"
TEXT 10, 155, \"TSS24.BF2\", 0, 1, 1, \"房号: ${ROOM_NUMBER}\"
TEXT 10, 180, \"TSS24.BF2\", 0, 1, 1, \"件数: ${ITEM_COUNT}\"
TEXT 10, 205, \"TSS24.BF2\", 0, 1, 1, \"类型: ${DEPOSIT_TYPE}\"
TEXT 10, 230, \"TSS24.BF2\", 0, 1, 1, \"位置: ${STORAGE_LOCATION}\"
TEXT 10, 255, \"TSS24.BF2\", 0, 1, 1, \"日期: $(date +%Y-%m-%d)\"
BAR 10, 280, 460, 2
TEXT 120, 290, \"TSS24.BF2\", 0, 1, 1, \"取件验证码: ${PICKUP_CODE}\"
PRINT 1
'''
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('192.168.1.100', 9100))
s.sendall(tspl.encode('utf-8'))
s.close()
print('打印指令已发送')
"
```

### 补打流程

若标签损坏或丢失需补打：

```bash
# 更新标签打印状态为"已补打"
lark-cli base +record-update \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{"标签打印状态": "已补打"}'
```

---

## 电子凭证发送流程

### 渠道一：飞书交互卡片

适用于宾客已关注酒店飞书机器人，或行李员内部流转通知。

```json
{
  "msg_type": "interactive",
  "card": {
    "config": { "wide_screen_mode": true },
    "header": {
      "title": { "tag": "plain_text", "content": "行李寄存凭证" },
      "template": "blue"
    },
    "elements": [
      {
        "tag": "div",
        "fields": [
          { "is_short": true, "text": { "tag": "lark_md", "content": "**寄存单号**\nLG-20260623-001" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**宾客姓名**\n张三" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**房号**\n1208" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**寄存件数**\n2 件" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**寄存类型**\n普通行李" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**寄存位置**\n一楼行李房" } }
        ]
      },
      {
        "tag": "div",
        "text": { "tag": "lark_md", "content": "**行李描述：**\n黑色28寸行李箱1个，红色手提袋1个" }
      },
      { "tag": "hr" },
      {
        "tag": "div",
        "text": { "tag": "lark_md", "content": "**寄存时间：** 2026-06-23 14:30" }
      },
      {
        "tag": "note",
        "elements": [
          { "tag": "plain_text", "content": "取件验证码: 8826 | 请妥善保管此凭证，取件时需出示验证码" }
        ]
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": { "tag": "plain_text", "content": "确认取件" },
            "type": "primary",
            "value": { "action": "claim_luggage", "deposit_number": "LG-20260623-001" }
          }
        ]
      }
    ]
  }
}
```

发送命令：

```bash
lark-cli im +send \
  --chat-id oc_xxxxxxxxxxxxx \
  --msg-type interactive \
  --content '<上述JSON>'
```

### 渠道二：短信

适用于宾客未关注飞书，或需要短信留存凭证。

**短信模板（已备案）：**

```
【瑞湾酒店】尊敬的{guest_name}，您的行李寄存凭证：单号{deposit_number}，{item_count}件，存放于{storage_location}。取件验证码：{pickup_code}。请妥善保管，取件时出示验证码。如有疑问请致电前台。
```

**发送示例：**

```bash
# 调用短信网关 API
curl -X POST "https://api.sms-provider.com/v1/send" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "13800138000",
    "template_id": "TPL_LUGGAGE_DEPOSIT",
    "params": {
      "guest_name": "张三",
      "deposit_number": "LG-20260623-001",
      "item_count": "2",
      "storage_location": "一楼行李房",
      "pickup_code": "8826"
    }
  }'
```

### 渠道三：微信模板消息

适用于宾客关注酒店微信公众号 / 小程序的场景。

**微信模板消息 JSON：**

```json
{
  "touser": "OPENID",
  "template_id": "TMPL_LUGGAGE_DEPOSIT",
  "url": "https://hotel.example.com/luggage/LG-20260623-001",
  "miniprogram": {
    "appid": "wx_hotel_appid",
    "pagepath": "pages/luggage/detail?number=LG-20260623-001"
  },
  "data": {
    "first": { "value": "您的行李已寄存成功", "color": "#173177" },
    "keyword1": { "value": "LG-20260623-001", "color": "#173177" },
    "keyword2": { "value": "张三 / 1208房", "color": "#173177" },
    "keyword3": { "value": "2件 普通行李", "color": "#173177" },
    "keyword4": { "value": "2026-06-23 14:30", "color": "#173177" },
    "keyword5": { "value": "取件验证码: 8826", "color": "#FF0000" },
    "remark": { "value": "请妥善保管此凭证，取件时需出示验证码。行李存放于一楼行李房。", "color": "#333333" }
  }
}
```

---

## 超期预警规则

系统按以下分级规则自动检测和推送超期行李预警：

### 预警级别

| 级别 | 触发条件 | 通知对象 | 通知方式 | 内容 |
|------|----------|----------|----------|------|
| 一级预警 | 寄存超过 24 小时 | 行李员 + 前台主管 | 飞书群消息 | "行李超24h提醒：{deposit_number}，宾客{guest_name}，{room_number}房" |
| 二级预警 | 寄存超过 48 小时 | 前台主管 + 客房经理 | 飞书群消息 + 飞书私聊 | "行李超48h警告：{deposit_number}，请尽快联系宾客{guest_name}（{phone}）" |
| 三级预警 | 寄存超过 72 小时 | 值班经理 + 安保主管 | 飞书群消息 + 短信 | "行李超72h紧急：{deposit_number}，宾客{guest_name}未取件，请启动处置流程" |

### 超期检查命令

```bash
# 24 小时超期检查
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{
    "conjunction": "and",
    "conditions": [
      {"field_name": "状态", "operator": "is", "value": ["待取"]},
      {"field_name": "寄存日期", "operator": "isLess", "value": ["24hoursAgo"]}
    ]
  }' \
  --fields '["寄存单号","宾客姓名","房号","联系方式","寄存日期"]' \
  --format json

# 48 小时超期检查（同上，value 改为 "48hoursAgo"）
# 72 小时超期检查（同上，value 改为 "72hoursAgo"）
```

### 定时任务

建议将超期检查设置为定时任务，每日 09:00、14:00、20:00 各执行一次：

```bash
# 使用 cron 或飞书自动化工作流
# 0 9,14,20 * * * python3 main.py check-overdue --type luggage --hours 24
# 0 9,14,20 * * * python3 main.py check-overdue --type luggage --hours 48
# 0 9,14,20 * * * python3 main.py check-overdue --type luggage --hours 72
```

---

## 调用示例

### 示例 1：宾客办理行李寄存

**用户输入：** "1208房的张三要寄存2件行李，一个黑色行李箱和一个红色手提袋，普通行李，放在一楼行李房"

**执行步骤：**

```bash
# Step 1: 查询当日序号
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"寄存日期","operator":"is","value":["TODAY"]}]}' \
  --fields '["寄存单号"]' --format json

# Step 2: 创建寄存记录
lark-cli base +record-create \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --fields '{
    "寄存单号": "LG-20260623-001",
    "宾客姓名": "张三",
    "房号": "1208",
    "入住房号": "1208",
    "联系方式": "13800138000",
    "寄存日期": "2026-06-23T14:30:00+08:00",
    "寄存件数": 2,
    "寄存类型": "普通行李",
    "寄存位置": "一楼行李房",
    "行李描述": "黑色行李箱1个，红色手提袋1个",
    "标签打印状态": "未打印",
    "取件验证码": "8826",
    "状态": "待取",
    "经办人": "行李员小李"
  }'

# Step 3: 打印标签 → Step 4: 发送凭证
```

### 示例 2：宾客取件

**用户输入：** "张三来取行李，验证码是8826"

**执行步骤：**

```bash
# Step 1: 按验证码 + 姓名查询
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"宾客姓名","operator":"is","value":["张三"]},{"field_name":"取件验证码","operator":"is","value":["8826"]},{"field_name":"状态","operator":"is","value":["待取"]}]}' \
  --format json

# Step 2: 核实信息，确认无误后更新状态
lark-cli base +record-update \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{
    "状态": "已取",
    "取件日期": "2026-06-24T10:15:00+08:00",
    "取件时间": "10:15",
    "取件经办人": "行李员小王"
  }'
```

### 示例 3：查询某房间寄存记录

**用户输入：** "帮我查一下1208房目前有没有寄存行李"

```bash
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"房号","operator":"is","value":["1208"]},{"field_name":"状态","operator":"is","value":["待取"]}]}' \
  --fields '["寄存单号","宾客姓名","寄存日期","寄存件数","行李描述","寄存位置"]' \
  --format json
```

### 示例 4：补打行李标签

**用户输入：** "LG-20260623-001的行李标签损坏了，需要补打"

```bash
# Step 1: 查询记录信息
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"寄存单号","operator":"is","value":["LG-20260623-001"]}]}' \
  --format json

# Step 2: 发送 TSPL 打印指令（同正常打印流程）

# Step 3: 更新打印状态
lark-cli base +record-update \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{"标签打印状态": "已补打"}'
```

### 示例 5：查看当日寄存台账

**用户输入：** "今天还有多少行李没取"

```bash
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{"conjunction":"and","conditions":[{"field_name":"寄存日期","operator":"is","value":["TODAY"]},{"field_name":"状态","operator":"is","value":["待取"]}]}' \
  --fields '["寄存单号","宾客姓名","房号","寄存件数","寄存类型","寄存位置","行李描述"]' \
  --format json
```

### 示例 6：超期行李处置

**用户输入：** "有没有超过48小时还没取的行李"

```bash
# 查询超 48 小时未取件记录
lark-cli base +record-list \
  --app-token Atj6bOVJtaDGSjspKDqcx3Jqnfd \
  --table-id tblMPvX3VKodb80I \
  --filter '{
    "conjunction": "and",
    "conditions": [
      {"field_name": "状态", "operator": "is", "value": ["待取"]},
      {"field_name": "寄存日期", "operator": "isLess", "value": ["48hoursAgo"]}
    ]
  }' \
  --fields '["寄存单号","宾客姓名","房号","联系方式","寄存日期","行李描述"]' \
  --format json

# 根据结果，逐一发送二级预警通知
```

---

## 与遗留物品 SKILL 的关系

行李寄存系统（hotel-luggage-storage）与遗留物品系统（hotel-lost-and-found）之间存在以下协作关系：

| 维度 | 行李寄存 | 遗留物品 |
|------|----------|----------|
| 触发场景 | 宾客主动寄存 | 宾客离店后发现遗留 |
| 编号前缀 | `LG-` | `LF-` |
| 数据表 | `tblMPvX3VKodb80I` | `tblgcBcPR9P8fina` |
| 状态流转 | 待取 → 已取 | 待认领 → 已联系宾客 → 已认领/已邮寄/已销毁/已移交公安 |
| 保管位置 | 一楼行李房 / 三楼长住行李房 | 客房部保险箱 / 前厅部保管柜 / 失物招领处 |
| 超期规则 | 24h / 48h / 72h 三级预警 | 30天 / 60天 / 90天 三阶段处理 |

**交叉场景：**
- 宾客寄存的行李中包含遗留物品 → 行李系统取件时发现遗留 → 转入遗留物品系统登记
- 遗留物品经确认后宾客来取 → 若行李寄存系统中有该宾客的寄存记录，可一并通知取件
- 两个系统共享宾客联系方式和房号信息，便于统一联系
