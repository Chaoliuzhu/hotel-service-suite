---
name: hotel-lost-and-found
description: 酒店遗留物品全流程管理——登记有图、保管有序、邮寄可查、超期可控。新增"随手拍"AI拍照识别和"快递站模式"存取流程。支持物品图片台账、重要物品保险箱管理、宾客自助查询、三渠道通知、多维表格表单兜底入口。
触发词：遗留物品、客遗物品、失物招领、捡到的、客人落下、遗落、捡到物品、物品登记、失物查询、认领物品、邮寄遗留、超期物品、遗留台账、随手拍、拍照登记、快递站模式
version: 3.0.0
---

# 酒店遗留物品管理系统

## 核心能力概述

本技能实现酒店遗留物品的全生命周期管理，覆盖从发现登记到最终处置的完整链路：

1. **物品登记**：发现遗留物品后立即登记，含物品描述、图片上传、发现地点记录
2. **图片台账**：物品图片自动归档至飞书云空间，支持图文对照管理
3. **重要物品管理**：贵重物品（电子产品、首饰珠宝、证件文件等）当天必须入保险箱保管
4. **宾客通知**：支持飞书卡片、短信、微信三渠道通知宾客认领
5. **邮寄服务**：支持快递邮寄，自动记录快递公司和运单号
6. **超期处理**：30天提醒 → 60天公示 → 90天处理，三级递进处置
7. **条码标签**：为每件物品打印条码标签，便于识别和盘点
8. **台账查询**：多维度查询遗留物品台账，支持按状态、时间、地点筛选

---

## 数据底座

本系统的数据存储使用飞书多维表格（Bitable）：

| 参数 | 值 |
|------|-----|
| `app_token` | `JJpTbxNJgaVojJsfUItcmvq5nqf` |
| `table_id` | `tblgcBcPR9P8fina` |

所有读写操作通过 `lark-cli base` 命令完成。

---

## 字段完整映射

以下为多维表格中全部 24 个字段及其在系统中的映射关系：

| 序号 | 字段名（多维表格） | 字段类型 | 枚举值 / 说明 | 系统变量映射 |
|------|---------------------|----------|----------------|--------------|
| 1 | 失物编号 | 文本 | 格式：`LF-YYYYMMDD-XXX`，如 `LF-20260623-001` | `lost_number` |
| 2 | 物品名称 | 文本 | 物品简称，如"iPhone 15" | `item_name` |
| 3 | 物品类别 | 单选 | `电子产品` / `首饰珠宝` / `证件文件` / `衣物包袋` / `其他` | `item_category` |
| 4 | 物品描述 | 文本 | 外观详细描述 | `item_description` |
| 5 | 物品明细 | 文本 | 物品内所含细项，如"内有身份证一张、银行卡两张" | `item_detail` |
| 6 | 物品图片 | 附件 | 支持多张图片上传 | `item_images` |
| 7 | 发现日期 | 日期 | ISO 8601 格式：`2026-06-23T09:00:00+08:00` | `found_datetime` |
| 8 | 发现地点 | 文本 | 详细地点描述 | `found_location` |
| 9 | 发现人 | 文本 | 发现物品的人员姓名 | `finder_name` |
| 10 | 捡拾地点 | 单选 | `客房` / `大堂` / `餐厅` / `泳池` / `停车场` / `会议室` | `pickup_location` |
| 11 | 捡拾人 | 文本 | 实际捡拾物品的工作人员姓名 | `picker_name` |
| 12 | 宾客姓名 | 文本 | 遗留物品所属宾客的姓名 | `guest_name` |
| 13 | 宾客联系方式 | 文本 | 宾客手机号码（11 位） | `guest_phone` |
| 14 | 宾客收件地址 | 文本 | 邮寄地址（邮寄时填写） | `guest_address` |
| 15 | 重要物品 | 单选 | `是` / `否`（电子产品/首饰珠宝/证件文件默认为"是"） | `is_important` |
| 16 | 储备保管位置 | 单选 | `客房部保险箱` / `前厅部保管柜` / `失物招领处` / `已返还宾客` | `storage_location` |
| 17 | 物品状态 | 单选 | `待认领` / `已联系宾客` / `已认领` / `已邮寄` / `已销毁` / `已移交公安` | `item_status` |
| 18 | 认领状态 | 单选 | `待认领` / `已认领` / `无人认领报备` | `claim_status` |
| 19 | 认领时间 | 日期 | ISO 8601 格式 | `claim_datetime` |
| 20 | 快递公司 | 文本 | 如"顺丰""中通""京东" | `courier_company` |
| 21 | 运单号 | 文本 | 快递运单号 | `tracking_number` |
| 22 | 邮寄日期 | 日期 | ISO 8601 格式 | `mail_datetime` |
| 23 | 领取签字备注 | 文本 | 宾客领取时的签字确认备注 | `claim_signature_note` |
| 24 | 天津瑞湾-遗留物品管理台账 | 文本 | 台账归档标记 / 审计追溯字段 | `ledger_ref` |

---

## 编号规则

失物编号生成规则：`LF-YYYYMMDD-XXX`

- `LF`：Lost & Found 固定前缀
- `YYYYMMDD`：发现日期（8 位）
- `XXX`：当日三位顺序号，从 `001` 开始递增

生成算法：
1. 查询多维表格中当日（`发现日期` 在 `[今日 00:00:00, 今日 23:59:59]` 范围内）的全部记录
2. 取最大序号 + 1，左补零至 3 位
3. 若当日无记录，则序号为 `001`

```bash
# 查询当日遗留物品记录数
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"发现日期","operator":"is","value":["TODAY"]}]}' \
  --fields '["失物编号"]'
```

---

## 登记操作流程

### 前置校验

在登记遗留物品前，必须确认以下信息已收集：

| 必填信息 | 对应字段 | 校验规则 |
|----------|----------|----------|
| 物品名称 | 物品名称 | 非空，1-50 个字符 |
| 物品类别 | 物品类别 | 必须在枚举值中 |
| 发现日期 | 发现日期 | ISO 8601 格式，不晚于当前时间 |
| 捡拾地点 | 捡拾地点 | 必须在枚举值中 |
| 发现人/捡拾人 | 发现人 / 捡拾人 | 至少填写其一 |

### 操作步骤

**Step 1：生成失物编号**

```bash
# 1. 查询当日已有记录数
TODAY_COUNT=$(lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"发现日期","operator":"is","value":["TODAY"]}]}' \
  --fields '["失物编号"]' \
  --format json | jq '.items | length')

# 2. 计算序号
SEQ=$(printf "%03d" $((TODAY_COUNT + 1)))

# 3. 拼接失物编号
LOST_NUMBER="LF-$(date +%Y%m%d)-${SEQ}"
```

**Step 2：判定重要物品**

重要物品判定规则——满足以下任一条件即标记为"是"：
- 物品类别为 `电子产品`、`首饰珠宝`、`证件文件`
- 物品描述中包含"现金""钥匙""护照""身份证""银行卡""合同"等关键词
- 用户明确标注 `--important`

```bash
# 自动判定逻辑
IMPORTANT="否"
if [[ "$ITEM_CATEGORY" == "电子产品" || "$ITEM_CATEGORY" == "首饰珠宝" || "$ITEM_CATEGORY" == "证件文件" ]]; then
  IMPORTANT="是"
fi
```

**Step 3：上传物品图片**

```bash
# 上传物品图片到飞书
lark-cli drive +upload \
  --file ./item_photo.jpg \
  --folder-token fldcnXXXXXXXXXXXXXX \
  --name "LF-20260623-001_物品照片_1.jpg"
```

**Step 4：写入多维表格**

```bash
lark-cli base +record-create \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --fields '{
    "失物编号": "LF-20260623-001",
    "物品名称": "iPhone 15",
    "物品类别": "电子产品",
    "物品描述": "黑色iPhone 15 Pro Max，带透明保护壳，屏幕无损坏",
    "物品明细": "手机1台，充电线1根",
    "发现日期": "2026-06-23T09:00:00+08:00",
    "发现地点": "302房间床头柜上",
    "发现人": "客房服务员小王",
    "捡拾地点": "客房",
    "捡拾人": "客房服务员小王",
    "宾客姓名": "李四",
    "宾客联系方式": "13900139000",
    "重要物品": "是",
    "储备保管位置": "客房部保险箱",
    "物品状态": "待认领",
    "认领状态": "待认领",
    "天津瑞湾-遗留物品管理台账": "LF-20260623-001"
  }'
```

**Step 5：打印条码标签**（详见"条码标签打印流程"）

**Step 6：通知宾客**（详见"宾客通知流程"）

---

## 重要物品当天入保险箱规则

### 触发条件

当遗留物品满足以下任一条件时，**必须在当天 18:00 前**送入客房部保险箱：

1. `重要物品` 字段值为 `是`
2. `物品类别` 为 `电子产品` / `首饰珠宝` / `证件文件`
3. 物品内含现金（无论金额）
4. 物品内含钥匙（含车钥匙、门禁卡）

### 保险箱操作流程

```
1. 客房主管确认物品信息 → 签字确认
2. 物品放入保险箱 → 拍照存档（保险箱编号 + 物品编号）
3. 更新多维表格「储备保管位置」为「客房部保险箱」
4. 保险箱钥匙由值班经理保管
5. 次日早班交接时逐一盘点确认
```

### 每日保险箱盘点

```bash
# 查询当前在保险箱中的全部物品
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"储备保管位置","operator":"is","value":["客房部保险箱"]},{"field_name":"物品状态","operator":"isNot","value":["已认领","已邮寄","已销毁","已移交公安"]}]}' \
  --fields '["失物编号","物品名称","物品类别","发现日期","宾客姓名"]' \
  --format json
```

---

## 宾客通知流程

### 渠道一：飞书卡片

适用于宾客已关注酒店飞书机器人的场景。

```json
{
  "msg_type": "interactive",
  "card": {
    "config": { "wide_screen_mode": true },
    "header": {
      "title": { "tag": "plain_text", "content": "遗留物品认领通知" },
      "template": "orange"
    },
    "elements": [
      {
        "tag": "div",
        "fields": [
          { "is_short": true, "text": { "tag": "lark_md", "content": "**失物编号**\nLF-20260623-001" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**物品名称**\niPhone 15" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**物品类别**\n电子产品" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**发现地点**\n302房间" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**发现日期**\n2026-06-23" } },
          { "is_short": true, "text": { "tag": "lark_md", "content": "**保管位置**\n客房部保险箱" } }
        ]
      },
      {
        "tag": "div",
        "text": { "tag": "lark_md", "content": "**物品描述：**\n黑色iPhone 15 Pro Max，带透明保护壳" }
      },
      { "tag": "hr" },
      {
        "tag": "note",
        "elements": [
          { "tag": "plain_text", "content": "请携带有效证件到前台认领，或联系我们安排邮寄。" }
        ]
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": { "tag": "plain_text", "content": "我要认领" },
            "type": "primary",
            "value": { "action": "claim_item", "lost_number": "LF-20260623-001" }
          },
          {
            "tag": "button",
            "text": { "tag": "plain_text", "content": "安排邮寄" },
            "type": "default",
            "value": { "action": "mail_item", "lost_number": "LF-20260623-001" }
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

**短信模板（已备案）：**

```
【瑞湾酒店】尊敬的{guest_name}，您在退房时可能遗留了{item_name}（失物编号：{lost_number}），发现于{pickup_location}。物品已妥善保管，请携带有效证件到前台认领，或致电{hotel_phone}安排邮寄。
```

**发送示例：**

```bash
curl -X POST "https://api.sms-provider.com/v1/send" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "13900139000",
    "template_id": "TPL_LOST_FOUND",
    "params": {
      "guest_name": "李四",
      "item_name": "iPhone 15",
      "lost_number": "LF-20260623-001",
      "pickup_location": "客房",
      "hotel_phone": "022-XXXXXXXX"
    }
  }'
```

### 渠道三：微信模板消息

```json
{
  "touser": "OPENID",
  "template_id": "TMPL_LOST_FOUND",
  "url": "https://hotel.example.com/lost-found/LF-20260623-001",
  "miniprogram": {
    "appid": "wx_hotel_appid",
    "pagepath": "pages/lost-found/detail?number=LF-20260623-001"
  },
  "data": {
    "first": { "value": "您有遗留物品待认领", "color": "#FF6600" },
    "keyword1": { "value": "LF-20260623-001", "color": "#173177" },
    "keyword2": { "value": "iPhone 15 Pro Max", "color": "#173177" },
    "keyword3": { "value": "302房间", "color": "#173177" },
    "keyword4": { "value": "2026-06-23", "color": "#173177" },
    "keyword5": { "value": "客房部保险箱（妥善保管中）", "color": "#173177" },
    "remark": { "value": "请携带有效证件到前台认领，或联系我们安排邮寄。如有疑问请致电前台。", "color": "#333333" }
  }
}
```

### 通知时机

| 时机 | 通知内容 | 渠道 |
|------|----------|------|
| 发现当日 | 首次通知宾客有遗留物品 | 飞书 + 短信 + 微信 |
| 发现后第 3 天 | 提醒宾客尽快认领 | 短信 |
| 发现后第 7 天 | 再次提醒 | 短信 + 电话 |
| 宾客回复认领 | 发送认领指引 | 飞书卡片 |
| 宾客回复邮寄 | 发送邮寄确认 | 短信 + 微信 |

---

## 邮寄流程

### 前置校验

邮寄前必须确认：
- `物品状态` 为 `待认领` 或 `已联系宾客`
- 宾客已确认邮寄意愿并提供收件地址
- 重要物品邮寄需宾客签署《重要物品邮寄授权书》

### 操作步骤

**Step 1：确认邮寄信息**

```bash
# 查询物品当前状态
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"失物编号","operator":"is","value":["LF-20260623-001"]}]}' \
  --format json
```

**Step 2：更新邮寄信息**

```bash
lark-cli base +record-update \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{
    "物品状态": "已邮寄",
    "认领状态": "已认领",
    "宾客收件地址": "北京市朝阳区xxx小区xxx号",
    "快递公司": "顺丰",
    "运单号": "SF1234567890",
    "邮寄日期": "2026-06-24T10:00:00+08:00"
  }'
```

**Step 3：发送邮寄通知**

```bash
# 通过短信通知宾客邮寄信息
curl -X POST "https://api.sms-provider.com/v1/send" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "13900139000",
    "template_id": "TPL_LOST_FOUND_MAIL",
    "params": {
      "guest_name": "李四",
      "item_name": "iPhone 15",
      "lost_number": "LF-20260623-001",
      "courier": "顺丰",
      "tracking": "SF1234567890"
    }
  }'
```

**Step 4：拍照存档**

邮寄前需对物品进行拍照存档：
1. 物品正面照
2. 物品细节照（含物品编号标签）
3. 包装照
4. 快递面单照

---

## 超期处理流程

### 三阶段递进处置

| 阶段 | 时间节点 | 处置动作 | 通知对象 | 系统状态更新 |
|------|----------|----------|----------|-------------|
| 第一阶段：提醒 | 发现后 30 天 | 发送最终提醒通知 | 宾客（短信 + 微信 + 电话） | `物品状态` 保持 `待认领` |
| 第二阶段：公示 | 发现后 60 天 | 进入无人认领公示期 | 内部管理层 | `认领状态` 更新为 `无人认领报备` |
| 第三阶段：处理 | 发现后 90 天 | 按物品类别进行最终处置 | 值班经理 + 安保主管 | `物品状态` 更新为 `已销毁` 或 `已移交公安` |

### 第一阶段：30 天提醒

```bash
# 查询超 30 天未认领物品
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{
    "conjunction": "and",
    "conditions": [
      {"field_name": "物品状态", "operator": "is", "value": ["待认领"]},
      {"field_name": "发现日期", "operator": "isLess", "value": ["30daysAgo"]}
    ]
  }' \
  --fields '["失物编号","物品名称","物品类别","发现日期","宾客姓名","宾客联系方式"]' \
  --format json
```

30 天提醒短信模板：

```
【瑞湾酒店】尊敬的{guest_name}，您遗留的{item_name}（编号{lost_number}）已在酒店保管超过30天。如仍需认领，请于7日内联系前台（{hotel_phone}），逾期将按酒店规定处理。
```

### 第二阶段：60 天公示

```bash
# 查询超 60 天未认领物品
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{
    "conjunction": "and",
    "conditions": [
      {"field_name": "物品状态", "operator": "is", "value": ["待认领"]},
      {"field_name": "发现日期", "operator": "isLess", "value": ["60daysAgo"]}
    ]
  }' \
  --format json
```

公示操作：
1. 更新 `认领状态` 为 `无人认领报备`
2. 在酒店内部管理系统中登记公示
3. 通知管理层

```bash
lark-cli base +record-update \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{"认领状态": "无人认领报备"}'
```

### 第三阶段：90 天处理

```bash
# 查询超 90 天未认领物品
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{
    "conjunction": "and",
    "conditions": [
      {"field_name": "物品状态", "operator": "is", "value": ["待认领"]},
      {"field_name": "认领状态", "operator": "is", "value": ["无人认领报备"]},
      {"field_name": "发现日期", "operator": "isLess", "value": ["90daysAgo"]}
    ]
  }' \
  --format json
```

最终处置方式：

| 物品类别 | 处置方式 | 状态更新 |
|----------|----------|----------|
| 电子产品 / 首饰珠宝 | 移交公安机关 | `物品状态` → `已移交公安` |
| 证件文件 | 移交公安机关 | `物品状态` → `已移交公安` |
| 衣物包袋 | 酒店统一销毁或捐赠 | `物品状态` → `已销毁` |
| 其他（低价值） | 酒店统一销毁 | `物品状态` → `已销毁` |

处置前必须：
1. 拍照存档（处置前最终状态照）
2. 值班经理签字确认
3. 更新多维表格所有相关字段
4. 在台账中记录处置详情

```bash
# 更新为已移交公安
lark-cli base +record-update \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{
    "物品状态": "已移交公安",
    "领取签字备注": "2026-09-21 移交XX派出所，接收人：警官张XX，移交单号：GA-20260921-001"
  }'

# 更新为已销毁
lark-cli base +record-update \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{
    "物品状态": "已销毁",
    "领取签字备注": "2026-09-21 由值班经理王XX监督销毁"
  }'
```

---

## 条码标签打印流程

### 打印机要求

- 类型：热敏标签打印机（同行李寄存系统共用）
- 标签尺寸：50mm x 30mm（推荐）
- 通信方式：TCP/IP（网口）
- 指令集：TSPL

### TSPL 打印指令

```tspl
SIZE 50 mm, 30 mm
GAP 2 mm, 0 mm
DIRECTION 1
REFERENCE 0, 0
SET TEAR OFF
SET CUTTER OFF
CLS

! 标题
TEXT 170, 5, "TSS24.BF2", 0, 1, 1, "遗留物品标签"

! 失物编号（大字）
TEXT 100, 25, "TSS24.BF2", 0, 1, 1, "LF-20260623-001"

! 条码（Code128）
BARCODE 130, 45, "128", 40, 1, 0, 2, 2, "LF-20260623-001"

! 物品信息
TEXT 10, 95, "TSS24.BF2", 0, 1, 1, "物品: iPhone 15"
TEXT 10, 115, "TSS24.BF2", 0, 1, 1, "类别: 电子产品"
TEXT 10, 135, "TSS24.BF2", 0, 1, 1, "地点: 302房间"
TEXT 10, 155, "TSS24.BF2", 0, 1, 1, "日期: 2026-06-23"

! 分割线
BAR 10, 175, 380, 2

! 重要物品标记
TEXT 130, 180, "TSS24.BF2", 0, 1, 1, "[重要物品] 保险箱保管"

PRINT 1
```

### 网络打印命令

```bash
python3 -c "
import socket
tspl = '''SIZE 50 mm, 30 mm
GAP 2 mm, 0 mm
DIRECTION 1
REFERENCE 0, 0
CLS
TEXT 170, 5, \"TSS24.BF2\", 0, 1, 1, \"遗留物品标签\"
TEXT 100, 25, \"TSS24.BF2\", 0, 1, 1, \"${LOST_NUMBER}\"
BARCODE 130, 45, \"128\", 40, 1, 0, 2, 2, \"${LOST_NUMBER}\"
TEXT 10, 95, \"TSS24.BF2\", 0, 1, 1, \"物品: ${ITEM_NAME}\"
TEXT 10, 115, \"TSS24.BF2\", 0, 1, 1, \"类别: ${ITEM_CATEGORY}\"
TEXT 10, 135, \"TSS24.BF2\", 0, 1, 1, \"地点: ${FOUND_LOCATION}\"
TEXT 10, 155, \"TSS24.BF2\", 0, 1, 1, \"日期: $(date +%Y-%m-%d)\"
BAR 10, 175, 380, 2
TEXT 130, 180, \"TSS24.BF2\", 0, 1, 1, \"${IMPORTANT_MARK}\"
PRINT 1
'''
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('192.168.1.100', 9100))
s.sendall(tspl.encode('utf-8'))
s.close()
print('打印指令已发送')
"
```

---

## 认领流程

### 现场认领

**Step 1：宾客身份验证**

```bash
# 查询待认领物品
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"宾客姓名","operator":"is","value":["李四"]},{"field_name":"物品状态","operator":"is","value":["待认领","已联系宾客"]}]}' \
  --format json
```

**Step 2：核验物品信息**

出示物品及照片，请宾客确认：
- 物品名称和描述是否匹配
- 物品细节是否一致

**Step 3：宾客签字确认**

```bash
lark-cli base +record-update \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{
    "物品状态": "已认领",
    "认领状态": "已认领",
    "认领时间": "2026-06-25T14:00:00+08:00",
    "储备保管位置": "已返还宾客",
    "领取签字备注": "宾客李四于2026-06-25 14:00签字确认领取，前台经办人：小张"
  }'
```

---

## 调用示例

### 示例 1：登记新发现的遗留物品

**用户输入：** "在302房间捡到一个黑色iPhone 15 Pro Max，带透明保护壳，应该是李四的，手机号13900139000"

**执行步骤：**

```bash
# Step 1: 生成编号 LF-20260623-001
# Step 2: 判定为重要物品（电子产品）
# Step 3: 创建记录
lark-cli base +record-create \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --fields '{
    "失物编号": "LF-20260623-001",
    "物品名称": "iPhone 15",
    "物品类别": "电子产品",
    "物品描述": "黑色iPhone 15 Pro Max，带透明保护壳，屏幕无损坏",
    "发现日期": "2026-06-23T09:00:00+08:00",
    "发现地点": "302房间床头柜上",
    "捡拾地点": "客房",
    "捡拾人": "客房服务员小王",
    "宾客姓名": "李四",
    "宾客联系方式": "13900139000",
    "重要物品": "是",
    "储备保管位置": "客房部保险箱",
    "物品状态": "待认领",
    "认领状态": "待认领"
  }'
# Step 4: 打印条码标签
# Step 5: 通知宾客（短信 + 飞书 + 微信）
# Step 6: 当天18:00前入保险箱
```

### 示例 2：宾客电话认领

**用户输入：** "李四打电话来说要认领iPhone 15，他下午过来取"

```bash
# Step 1: 查询记录
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"宾客姓名","operator":"is","value":["李四"]},{"field_name":"物品状态","operator":"is","value":["待认领"]}]}' \
  --format json

# Step 2: 更新状态为"已联系宾客"
lark-cli base +record-update \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{"物品状态": "已联系宾客"}'

# Step 3: 回复确认信息
```

### 示例 3：安排快递邮寄

**用户输入：** "李四的iPhone 15要邮寄，用顺丰，单号SF1234567890，地址是北京市朝阳区xxx小区"

```bash
lark-cli base +record-update \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --record-id recXXXXXXXXXXXXXX \
  --fields '{
    "物品状态": "已邮寄",
    "认领状态": "已认领",
    "宾客收件地址": "北京市朝阳区xxx小区xxx号",
    "快递公司": "顺丰",
    "运单号": "SF1234567890",
    "邮寄日期": "2026-06-24T10:00:00+08:00",
    "储备保管位置": "已返还宾客"
  }'
```

### 示例 4：查询当前待认领物品清单

**用户输入：** "目前还有哪些遗留物品没有被认领"

```bash
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"物品状态","operator":"is","value":["待认领","已联系宾客"]}]}' \
  --fields '["失物编号","物品名称","物品类别","发现日期","发现地点","宾客姓名","储备保管位置","重要物品"]' \
  --format json
```

### 示例 5：查看超期物品

**用户输入：** "有没有超过60天还没人来认领的物品"

```bash
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{
    "conjunction": "and",
    "conditions": [
      {"field_name": "物品状态", "operator": "is", "value": ["待认领"]},
      {"field_name": "发现日期", "operator": "isLess", "value": ["60daysAgo"]}
    ]
  }' \
  --fields '["失物编号","物品名称","物品类别","发现日期","宾客姓名","宾客联系方式","储备保管位置"]' \
  --format json

# 对查到的记录逐一更新认领状态为"无人认领报备"
```

### 示例 6：按房间查询遗留物品

**用户输入：** "506房间有没有遗留什么东西"

```bash
lark-cli base +record-list \
  --app-token JJpTbxNJgaVojJsfUItcmvq5nqf \
  --table-id tblgcBcPR9P8fina \
  --filter '{"conjunction":"and","conditions":[{"field_name":"发现地点","operator":"contains","value":["506"]}]}' \
  --fields '["失物编号","物品名称","物品类别","发现日期","物品状态","储备保管位置"]' \
  --format json
```

---

## 与行李寄存 SKILL 的关系

遗留物品系统（hotel-lost-and-found）与行李寄存系统（hotel-luggage-storage）之间存在以下协作关系：

| 维度 | 遗留物品 | 行李寄存 |
|------|----------|----------|
| 触发场景 | 宾客离店后发现遗留 | 宾客主动寄存 |
| 编号前缀 | `LF-` | `LG-` |
| 数据表 | `tblgcBcPR9P8fina` | `tblMPvX3VKodb80I` |
| 状态流转 | 待认领 → 已联系宾客 → 已认领/已邮寄/已销毁/已移交公安 | 待取 → 已取 |
| 保管位置 | 客房部保险箱 / 前厅部保管柜 / 失物招领处 | 一楼行李房 / 三楼长住行李房 |
| 超期规则 | 30天 / 60天 / 90天 三阶段处理 | 24h / 48h / 72h 三级预警 |

**交叉场景：**
- 宾客来取寄存行李时，可同步告知是否有遗留物品 → 一并处理
- 遗留物品系统中查到的宾客联系方式，可同步更新到行李寄存系统的提醒通知中
- 两个系统共享打印机设备（热敏标签打印机），使用不同的标签模板区分
- 月度盘点时，两个系统的台账应合并盘点

---

## 随手拍 AI 拍照识别

### 功能概述

"随手拍"功能同样适用于遗留物品登记。当员工发现遗留物品后，直接拍照发送给飞书 BOT，AI 自动识别物品信息（名称、类别、颜色、品牌、状态等），生成确认卡片供员工核对后一键写入台账。

### 工作流程

```
发现遗留物品 → 拍照发送给BOT → AI分析照片 → 提取物品信息 → 生成确认卡片 → 补充发现人/地点 → 确认 → 写入台账 → 通知宾客
```

### AI 识别字段（遗留物品场景）

| 字段 | 说明 | 示例 |
|------|------|------|
| 物品名称 | 物品类型 | 手机、钱包、衣物、证件、充电器 |
| 物品类别 | 五分类 | 电子产品/首饰珠宝/证件文件/衣物包袋/其他 |
| 详细描述 | 外观特征 | 黑色iPhone 15 Pro Max，带透明保护壳 |
| 主要颜色 | 外观颜色 | 黑色 |
| 品牌 | 如可识别 | Apple、LV、Nike |
| 物品状态 | 外观评估 | 完好/有使用痕迹/破损 |
| 重要物品标记 | 是否需入保险箱 | 是(电子产品/首饰/证件自动标记) |
| 置信度 | AI识别准确度 | 0.0 ~ 1.0 |

### 确认卡片

AI 识别完成后，系统发送橙色主题飞书卡片，包含:
- AI 识别结果（含置信度）
- 重要物品警告（如适用："需当天18:00前入保险箱"）
- 发现信息区域（发现人、地点、宾客信息）
- **确认登记** 按钮：写入台账、打印标签、通知宾客
- **需要修改** 按钮：引导补充信息

### CLI 使用

```bash
# 随手拍遗留物品登记
python main.py snap --photo /path/to/item.jpg --mode lost_found \
    --finder "客房服务员小王" --room 302 --guest "李四" --phone 13900139000
```

### 照片规则

**重要: 拍照仅在登记环节，认领环节无需拍照。**

| 环节 | 是否拍照 | 说明 |
|------|----------|------|
| 登记（发现） | 必须拍照 | AI 识别物品信息，作为台账图片存档 |
| 认领/邮寄 | 无需拍照 | 仅需核验身份或扫码即可认领 |

注意: 邮寄场景下仍需拍照存档（物品照、包装照、快递面单照），但这属于邮寄流程的一部分，而非"随手拍"。

---

## 快递站模式

### 设计理念

遗留物品管理同样遵循"快递站模式"的核心理念: **存入拍照、取出扫码**。

| 环节 | 快递站 | 酒店遗留物品 |
|------|--------|-------------|
| 存入 | 扫码→拍照→上架 | 拍照→AI识别→贴标签→入保险箱 |
| 取出 | 报取件码→验证→取走 | 核验身份→签字→认领/邮寄 |
| 通知 | 短信+APP推送 | 飞书卡片+短信+微信+电话 |
| 超期 | 3天催取→7天退回 | 30天提醒→60天公示→90天处理 |

### 存入流程 (deposit)

```python
from workflow.express_mode import ExpressModeProcessor

processor = ExpressModeProcessor()

result = processor.deposit_item(
    photo="/path/to/item.jpg",
    context="lost_found",
    operator="客房服务员小王",
    finder="客房服务员小王",
    found_location="302房间床头柜",
    room="302",
    guest_name="李四",
    guest_phone="13900139000",
)

print(result.summary())
# result.number -> "LF-20260623-001"
# result.is_valuable -> True (电子产品自动标记)
# result.storage_location -> "客房部保险箱"
```

### 认领流程 (pickup) — 无需拍照

```python
# 现场认领
result = processor.pickup_item(
    scan_code_or_number="LF-20260623-001",
    claimer="李四",
    operator="前台小张",
)

print(result.summary())
# result.success -> True
# result.guest_name -> "李四"
```

### 超期管理 (催取)

```python
# 检查所有超期物品
overdue = processor.check_and_notify_overdue()

# overdue["lost_found"] 包含:
# - 30天: 第一阶段-提醒 (发送最终通知)
# - 60天: 第二阶段-公示 (无人认领报备)
# - 90天: 第三阶段-处理 (移交公安/销毁)
```

### BOT 消息处理

当员工向 BOT 发送遗留物品照片或文字时:

| 消息 | 触发动作 |
|------|----------|
| 发送照片 | AI 识别 → 遗留物品确认卡片 |
| "遗留"/"捡到"/"客遗" | 显示遗留物品登记引导 |
| "查询 302" | 搜索 302 房间的遗留物品 |
| "查询 李四" | 搜索李四的遗留物品记录 |
| "状态" | 显示今日遗留物品概览 |

```bash
# 查看当日遗留物品状态
python main.py express-status
```

---

## 表单兜底入口

### 设计目的

当 AI BOT 不可用时（网络故障、维护升级等），员工可通过多维表格的"收集表单"视图手动登记遗留物品。
表单字段覆盖登记所需的全部信息，提交后自动写入主台账。

### 创建表单

```bash
# 创建遗留物品收集表单
python main.py form-setup --type lost-found

# 创建所有表单（行李+遗留物品）
python main.py form-setup --type all
```

### 使用方式

1. 管理员执行 `form-setup` 命令创建表单
2. 将表单链接放入 BOT 菜单、群公告或工作台
3. 员工在 AI 不可用时直接打开链接手动填写:
   - 物品名称 (必填)
   - 物品类别 (必填)
   - 捡拾地点 (必填)
   - 发现人 (必填)
   - 物品描述 (选填)
   - 宾客姓名/电话 (选填)
4. 提交后数据自动写入多维表格主台账
5. 系统按规则自动判定重要物品并分配保管位置

### 双入口架构总结

```
入口A (AI智能): 拍照发BOT → AI识别 → 确认卡片 → 自动录入 → 打印标签 → 通知宾客
入口B (表单兜底): 多维表格表单 → 手动填写 → 自动同步 → 打印标签 → 通知宾客
```

两个入口最终写入同一张多维表格 (`JJpTbxNJgaVojJsfUItcmvq5nqf` / `tblgcBcPR9P8fina`)，数据完全一致。

### 容灾切换

| 场景 | 推荐入口 | 说明 |
|------|----------|------|
| 正常运行 | 入口A (AI) | 拍照即登记，效率最高 |
| AI 服务不可用 | 入口B (表单) | 手动填写，数据不丢失 |
| 网络中断 | 离线记录 | 先拍照+纸笔记录，恢复后补录 |
| 批量登记 | 入口B (表单) | 表格支持批量导入 |
