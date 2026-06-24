# SKILL Review & Market Research Report

**Generated:** 2025-05-28  
**Scope:** SKILL工厂 (Skill Factory) review + International/Domestic Sales Methodology Research  
**Target:** Tianjin Ruiwan (天津瑞湾开元名都酒店) Hotel Sales Workflow Optimization

---

## Part 1: SKILL工厂 (Skill Factory) Review

### 1.1 Overview from Feishu Bitable (工具目录总览)

The SKILL工厂 (`hotel-skill-forge`) is a **Skill lifecycle management system** designed for the Delonix (德胧) AI ecosystem. It appears in two versions in the master tool catalog:

| Attribute | hotel-skill-forge v1 (Archived) | hotel-skill-forge v2 (Active) |
|---|---|---|
| **Record ID** | recvkSMf4vnWdd | recvkSMf4vFbmB |
| **Version** | v1 | v2 |
| **Status** | Archived (已被v2替代) | Under Development (开发中) |
| **Priority** | P2 General | P1 Important |
| **Domain** | SKILL体系 | SKILL体系 |
| **Positioning** | Skill生成器 | Skill全生命周期管理(SkillOpt闭环) |
| **Dependencies** | None | None |

A second data snapshot (from the 2025-05-28 sync) shows `hotel-skill-forge` v2 at **Production Ready (生产可用)** status, indicating it successfully graduated from development.

### 1.2 Skills Table Records

The skills table (技能工具库) contains **no direct skill-forge installation packages or GitHub links** - the SKILL工厂 is an infrastructure/meta-tool rather than an end-user skill. However, it is closely related to the **Eval quality framework** documented in the experience library.

### 1.3 Experience Library Findings

Two critical records directly reference the SKILL工厂:

#### Record 1: "SKILL工厂三层架构开发 x WIKI RAG Bailian API升级"
- **Source AI:** Claw (小柱)
- **Achievement:** 
  - WIKI RAG upgraded to v4.0 using Bailian API (qwen3.6-plus + text-embedding-v3, BM25+FAISS hybrid recall)
  - SKILL工厂 upgraded to **v3.1**
  - Layer1 forced to reference 智慧中枢 (wisdom hub)
  - lark-cli authorization completed, successfully writing to Feishu
- **Problems Identified:**
  - P0: WIKI RAG scripts/ directory was empty, had to use Ollama local models
  - P1: API Key was hardcoded, URL was incorrect, Layer2 was not writing files
  - P3: PLAN layer had no real Delonix knowledge injection, 大佬智慧库 not integrated
- **Solutions Implemented:**
  - Created `delonix-wiki-rag/scripts/rag_pipeline.py` with Bailian API
  - Fixed `factory_pipeline.py`: environment variable API keys, URL correction, Layer2 writes SKILL.md, Feishu bitable write-in
  - Layer1 `plan_research()` forced pre-load of `dlx-wisdom-hub`, all 7 PLAN tasks injected with WIKI chunks + executive decision wisdom

#### Record 2: "Skill开发质量保障" (Eval Quality Framework)
- **Source AI:** 德胧AI龙虾军团
- **Achievement:** 9 Skills all passed Eval, **98.8% pass rate** (85/85 expectations)
- **Skills Evaluated:** dlx-content-strategy, hotel-skill-generator, market-probe, dlx-copywriting, dlx-revenue-management, colleague, hotel-xuantui, dlx-customer-research, dlx-brainstorming
- **Framework:** eval_metadata.json (4 test cases + structured assertions), EVAL-GUIDE.md (grading guide), grade_eval.py (auto-scoring script)
- **Key Lesson:** "Eval is not testing for testing's sake - it's a quality gate. Changes must trigger re-evaluation."

### 1.4 SKILL工厂 Architecture Summary

```
SKILL工厂 Three-Layer Architecture (v3.1):
┌─────────────────────────────────────────┐
│ Layer 1: PLAN (计划层)                   │
│ - Research & requirements gathering      │
│ - References dlx-wisdom-hub (大佬智慧)   │
│ - WIKI RAG knowledge injection           │
├─────────────────────────────────────────┤
│ Layer 2: BUILD (构建层)                  │
│ - Generates SKILL.md files               │
│ - Writes to Feishu bitable               │
│ - API Key via environment variables      │
├─────────────────────────────────────────┤
│ Layer 3: EVAL (验证层)                   │
│ - 4 test cases per Skill                 │
│ - Structured assertions (PASS/FAIL)      │
│ - A/B/C/D grading system                 │
│ - 98.8% pass rate benchmark             │
└─────────────────────────────────────────┘
```

### 1.5 Assessment for Tianjin Ruiwan

| Dimension | Assessment |
|---|---|
| **What it was designed to do** | Automate the full lifecycle of AI Skill creation: research -> build -> test -> deploy. Essentially a "Skill that makes Skills." |
| **Current version** | v3.1 (experience library), v2 in master catalog. Production-ready status achieved. |
| **Practical value for hotel sales** | **Medium-High.** The SKILL工厂 itself is meta-infrastructure, but its output - domain-specific Skills like `hotel-xuantui` (选推), `dlx-copywriting`, `dlx-revenue-management` - are directly valuable for hotel marketing operations. |
| **What can be reused** | (1) The three-layer PLAN/BUILD/EVAL architecture is a proven pattern for creating new sales Skills; (2) The Eval quality gate methodology ensures any new sales Skill meets standards before deployment; (3) WIKI RAG integration with Bailian API provides a knowledge retrieval backbone that can inject hotel-specific context (brand standards, competitor data, pricing intelligence) into generated Skills. |
| **What needs iteration** | (1) No dedicated sales CRM or MICE pipeline Skill exists yet - the factory should produce one; (2) The `hotel-outreach-tracker` and `hotel-dormant-activator` are still in "planning" status - these are critical for sales; (3) Integration with external sales methodologies (MEDDIC, SPIN) has not been attempted. |

---

## Part 2: International & Domestic Market Research - Sales SKILLs/Methodologies

### 2.1 Hotel Sales CRM Methodologies

#### A. Salesforce Hospitality CRM
- **Source:** [Salesforce Travel & Hospitality](https://www.salesforce.com/travel-hospitality-transportation/hospitality/)
- **Core Methodology:**
  - **Guest Journey Orchestration:** Unifies data sources to strategically enhance guest experiences, proactively deliver on preferences, and anticipate future needs
  - **Agentforce AI:** AI agents that search/summarize data, offer proactive suggestions, and autonomously execute actions
  - **AI Concierge:** White-glove service automation
  - **Tableau Next + Data 360:** Predictive insights for smarter decision-making
  - **Lead Management:** Pursuing leads, scheduling meetings with potential partners
- **Adaptation for Tianjin Ruiwan:**
  - The guest journey orchestration concept maps directly to the hotel's existing "private domain" (私域) strategy via 百达屋 membership data
  - AI concierge concept aligns with the existing 神灯AI dialogue system
  - Lead management maps to `hotel-outreach-tracker` (currently in planning)
- **Priority:** HIGH - The conceptual framework is directly applicable even without purchasing Salesforce

#### B. Cloudbeds Hotel CRM Ecosystem
- **Source:** [Cloudbeds - 20 Best CRM Systems for Hotels](https://www.cloudbeds.com/articles/hotel-crm-system/)
- **Core Methodology:**
  - **Unified Guest Profiles:** Single view of every guest with preferences and spending habits
  - **Automated Profile Hygiene:** Nightly merge of duplicate profiles across properties
  - **Trigger-based Campaigns:** Automated marketing based on guest segments and stay milestones
  - **Sales Pipeline Management:** Track and nurture leads, monitor performance (via HubSpot integration)
  - **Reservation Sales Modules:** Virtual telephony and chat support for sales coaching (via Navis)
- **Adaptation for Tianjin Ruiwan:**
  - The unified guest profile concept should be implemented as a Skill that consolidates PMS + 百达屋 + OTA data
  - Trigger-based campaigns map to the `hotel-dormant-activator` concept (awakening 53% zero-output enterprise cards)
  - Profile hygiene automation is relevant for cleaning up the existing client database
- **Priority:** MEDIUM-HIGH - Practical operational patterns that can be encoded into Skills

#### C. Revinate Marketing CRM
- **Source:** [Revinate Marketing](https://www.revinate.com/hotel-software/revinate-marketing/)
- **Core Methodology:**
  - **Guest Data Platform:** Aggregates guest data from PMS, CRM, and other sources
  - **Hyper-segmentation:** AI-powered guest segmentation for targeted campaigns
  - **Email Marketing Automation:** Automated email campaigns with high ROI
  - **RFM Analysis:** Recency, Frequency, Monetary value analysis for guest scoring
- **Adaptation for Tianjin Ruiwan:**
  - RFM analysis framework can be directly applied to enterprise card scoring (`hotel-enterprise-scoring`)
  - Hyper-segmentation logic should inform the `hotel-private-domain` Skill design
  - Email automation patterns can be adapted for WeChat/企业微信 messaging
- **Priority:** MEDIUM - The segmentation methodology is more valuable than the platform itself

#### D. D-EDGE CRM (European hospitality specialist)
- **Source:** [D-EDGE CRM](https://www.d-edge.com/zh-hans/product_family/customer-relationship-management-zh-hans/)
- **Core Methodology:**
  - Personalized guest experience management
  - Pre-stay, in-stay, and post-stay communication automation
  - Direct booking optimization
- **Adaptation for Tianjin Ruiwan:**
  - The pre/in/post-stay communication framework can be applied to MICE group management
  - Direct booking optimization patterns relevant for reducing OTA dependency
- **Priority:** LOW-MEDIUM

### 2.2 MICE Market Development Frameworks

#### A. Thynk.Cloud MICE Strategy
- **Source:** [5 Strategies to Attract MICE Customers](https://thynk.cloud/blog/how-to-attract-mice-clients-to-your-hotel)
- **Core Methodology:**
  1. **Data-Driven Targeting:** Track client preferences/behaviors via CRM; centralized data for demand forecasting
  2. **Customized Packaging:** Tiered packages (Standard to VIP); include digital amenities for hybrid events
  3. **Lifecycle Relationship Management:** Continuous feedback loops; maintain engagement between events
  4. **Space & Tech Optimization:** Adaptable multi-functional rooms with integrated technology
  5. **Hyper-Personalization:** Use CRM history for on-site personalization (branded decor, custom menus, welcome kits)
  6. **Curated Downtime:** Regional partnerships for authentic local experiences
  7. **Frictionless Logistics:** End-to-end travel solutions bundling transport, lodging, events
- **Adaptation for Tianjin Ruiwan:**
  - **Directly applicable to current MICE push** - the Beijing outreach to 中国智慧会展集团 is a perfect use case
  - Tiered packaging should be encoded as a Skill that generates MICE proposals automatically
  - Tianjin-specific: leverage 深海温泉SPA and 杭帮菜/江西菜 as "curated downtime" differentiators
  - The "frictionless logistics" concept should integrate with the hotel's meeting room booking system
- **Priority:** CRITICAL - This is the most immediately actionable framework for the current sales push

#### B. Cvent MICE Framework
- **Source:** [Cvent - What Is MICE?](https://www.cvent.com/en/blog/hospitality/what-is-mice)
- **Core Methodology:**
  - Comprehensive MICE lifecycle management platform
  - RFP (Request for Proposal) management and response automation
  - Attendee registration and management
  - Venue sourcing and group block management
- **Adaptation for Tianjin Ruiwan:**
  - RFP response automation should be built as a Skill - auto-generate professional MICE proposals
  - Group block management maps to PMS integration needs
- **Priority:** HIGH - RFP automation is a quick win

#### C. PriceLabs MICE Pricing
- **Source:** [MICE Hotel Market: Attract & Price Group Events](https://hello.pricelabs.co/blog/mice-hotel-market-attract-price-group-events/)
- **Core Methodology:**
  - Dynamic group pricing models
  - Displacement analysis (group vs. transient revenue optimization)
  - Seasonal MICE demand forecasting
- **Adaptation for Tianjin Ruiwan:**
  - Should be integrated with `hotel-rev-ai` (AI revenue management engine, currently in planning)
  - Displacement analysis is critical for the hotel's current 36.1% completion rate challenge
- **Priority:** HIGH - Revenue optimization for MICE vs. transient is a key decision point

### 2.3 B2B Enterprise Sales Playbooks

#### A. MEDDPICC (Evolution of MEDDIC)
- **Source:** [B2B Sales Methodologies Compared](https://theb2bplaybook.com/best-sales-methodologies)
- **Core Framework - 8 Qualification Dimensions:**
  1. **M**etrics - Quantify the economic impact
  2. **E**conomic Buyer - Identify the financial decision maker
  3. **D**ecision Criteria - Understand evaluation standards
  4. **D**ecision Process - Map the approval journey
  5. **P**aper Process - Navigate legal/procurement
  6. **I**dentify Pain - Consequences of not solving the problem
  7. **C**hampion - Find internal advocates
  8. **C**ompetition - Know your rivals
- **Adaptation for Tianjin Ruiwan:**
  - **Directly applicable to enterprise card sales.** When approaching 央国企 clients:
    - Metrics: Quantify room-night savings, travel cost reduction
    - Economic Buyer: Identify the administrative/travel manager
    - Decision Criteria: Understand their hotel selection standards
    - Champion: Find the internal person who recommends the hotel
  - Should be encoded as a sales qualification checklist Skill
- **Priority:** CRITICAL - This is the most structured approach for the hotel's B2B enterprise sales

#### B. SPIN Selling
- **Source:** [Sales Qualification Frameworks Comparison](https://www.saber.app/blog/sales-qualification-frameworks-comparison)
- **Core Framework - Questioning Sequence:**
  1. **S**ituation questions - Understand the prospect's context
  2. **P**roblem questions - Identify operational pain points
  3. **I**mplication questions - Explore consequences of inaction
  4. **N**eed-Payoff questions - Guide toward solution commitment
- **Adaptation for Tianjin Ruiwan:**
  - Excellent for initial enterprise client meetings (e.g., MICE outreach visits)
  - Situation: "How does your company currently handle business travel to Tianjin?"
  - Problem: "What challenges do you face with your current hotel arrangements?"
  - Implication: "How much time/money is lost when employees book scattered hotels?"
  - Need-Payoff: "If we could consolidate all your Tianjin travel into one partner with guaranteed rates..."
- **Priority:** HIGH - The questioning methodology should be embedded in sales training Skills and talk track generators

#### C. Challenger Sale
- **Source:** [B2B Sales Methodologies Compared](https://eagr.ai/blog/b2b-sales-methodologies-compared)
- **Core Framework:**
  - **Teach:** Deliver novel insights the buyer hasn't considered
  - **Tailor:** Customize message to prospect's unique environment
  - **Take Control:** Confidently direct the commercial dialogue
- **Adaptation for Tianjin Ruiwan:**
  - The "teaching" approach is powerful for MICE sales: "Did you know that consolidating your Tianjin meeting spend with one hotel partner can reduce your total event cost by 15-20%?"
  - Aligns with Delonix's AI capabilities as a differentiator - "teach" clients about AI-powered hotel experiences
  - The 德胧AI虫洞 concept IS the Challenger Sale insight - using AI as the teaching hook
- **Priority:** HIGH - Natural fit with Delonix's AI differentiation strategy

### 2.4 Chinese Hotel Industry Sales Tools & Methodologies

#### A. 迈点 (Meadin) Brand Development Framework
- **Source:** [第十四届迈点品牌发展大会](https://cn.chinadaily.com.cn/a/202506/23/WS6858ed18a31009d21e5bdff2.html)
- **Core Methodology:**
  - Brand index scoring system for hotel brands in China
  - Market positioning analysis across brand categories
  - Digital transformation trend tracking
  - Investment and operations benchmarking
- **Adaptation for Tianjin Ruiwan:**
  - Meadin's brand index methodology can inform competitive positioning analysis
  - Their digital transformation reports provide market context for AI investment decisions
- **Priority:** MEDIUM - Useful for strategic context, not direct sales execution

#### B. KPMG China Hotel Resilience Report 2025
- **Source:** [KPMG - 破局与重生: 2025年中国酒店业的韧性之路](https://assets.kpmg.com/content/dam/kpmgsites/cn/pdf/zh/2025/11/the-resilience-road-of-china-s-hotel-industry-in-2025.pdf)
- **Core Methodology:**
  - Market cycle analysis and recovery pattern identification
  - Operational resilience frameworks
  - Revenue management adaptation strategies
- **Adaptation for Tianjin Ruiwan:**
  - Provides macro context for Tianjin market conditions
  - Revenue management strategies relevant to the 36.1% completion rate challenge
- **Priority:** MEDIUM - Strategic context

#### C. 中国饭店协会 (China Hotel Association) Standards
- **Source:** [2025中国酒店业发展报告](https://culture-travel.cctv.com/2025/04/23/ARTI0nTtKzfi6LtPx3gPuoPv250423.shtml)
- **Core Methodology:**
  - National hotel industry development guidelines
  - Quality standards and certification frameworks
  - Digital transformation roadmaps for Chinese hotels
- **Adaptation for Tianjin Ruiwan:**
  - Certification standards relevant for positioning (携程五钻 is already leveraged)
  - Digital transformation roadmap aligns with Delonix AI strategy
- **Priority:** LOW-MEDIUM - Compliance/positioning context

#### D. 纷享销客 (Fxiaoke) Hotel CRM
- **Source:** [酒店行业CRM软件选型指标](https://www.fxiaoke.com/crm/information-75388.html)
- **Core Methodology:**
  - 9 core dimensions for hotel CRM selection
  - Intelligent customer operations system
  - Sales pipeline management for Chinese enterprise sales
  - WeChat/企业微信 integration
- **Adaptation for Tianjin Ruiwan:**
  - The 9-dimension CRM framework is directly applicable to building a hotel sales Skill
  - WeChat/企业微信 integration patterns are essential for Chinese market execution
- **Priority:** MEDIUM-HIGH - Practical CRM architecture for Chinese hotel sales

### 2.5 新质生产力 (New Quality Productive Forces) Industry Classification

#### A. National Statistical Classification Framework
- **Source:** [工业战略性新兴产业分类目录（2023）](https://tjj.sh.gov.cn/gjbz/20240104/2fee91d89586425cb0f3069bd5e93a17.html) / [国家统计局](https://www.stats.gov.cn/zt_18555/zthd/sjtjr/tjr15/tjkpzs/202409/t20240914_1956499.html)
- **Core Framework - Strategic Emerging Industries (9 categories):**
  1. 新一代信息技术产业 (Next-gen IT)
  2. 高端装备制造产业 (High-end Equipment Manufacturing)
  3. 新材料产业 (New Materials)
  4. 生物产业 (Biotech)
  5. 新能源汽车产业 (NEV)
  6. 新能源产业 (New Energy)
  7. 节能环保产业 (Energy Conservation & Environmental Protection)
  8. 数字创意产业 (Digital Creative Industries)
  9. 相关服务业 (Related Services)
- **Relevance to Tianjin Ruiwan Sales:**
  - **数字创意产业 (Category 8)** and **相关服务业 (Category 9)** are most relevant for hotel/MICE targeting
  - Enterprises in these categories are high-value prospects for corporate card and MICE business
  - Can be used as a **client scoring dimension** in `hotel-enterprise-scoring` - enterprises in strategic emerging industries may have higher travel budgets and more MICE needs
- **Priority:** MEDIUM - Useful as a client segmentation/prospecting dimension

#### B. 新质生产力 x AI Integration Framework
- **Source:** [国家发改委 - 加快形成新质生产力](https://www.ndrc.gov.cn/wsdwhfz/202402/t20240206_1363980.html)
- **Core Methodology:**
  - Technology innovation as the primary driver
  - Industrial upgrading through digitalization
  - Green development integration
  - Talent ecosystem building
- **Adaptation for Tianjin Ruiwan:**
  - Delonix's AI strategy IS a 新质生产力 narrative - position the hotel as "新质生产力赋能酒店"
  - Use this framework in enterprise client pitches: "Partner with an AI-empowered hotel that represents 新质生产力 in hospitality"
  - The GEO/SEO content strategy should incorporate 新质生产力 keywords
- **Priority:** MEDIUM - Powerful narrative framing for government/SOE clients

---

## Part 3: Priority Adoption Matrix

| Priority | Methodology/Skill | Source | Action for Tianjin Ruiwan | Timeline |
|---|---|---|---|---|
| **P0 Critical** | MICE Lifecycle Management (Thynk.Cloud) | International | Build MICE proposal generator Skill; tiered packaging; CRM-driven targeting | Immediate (aligns with Beijing MICE outreach) |
| **P0 Critical** | MEDDPICC Sales Qualification | International | Encode as enterprise card sales qualification checklist; train sales team | Immediate (5月收官冲刺 needs structured pipeline) |
| **P0 Critical** | SKILL工厂 Eval Framework | Internal (Delonix) | Apply PLAN/BUILD/EVAL to create new sales Skills; maintain 98.8% quality bar | Ongoing |
| **P1 High** | SPIN Selling Questioning | International | Embed in sales talk track generator; use for enterprise client first meetings | 1-2 weeks |
| **P1 High** | Challenger Sale (Teach/Tailor/Control) | International | Use 德胧AI虫洞 as the "teaching hook" in enterprise pitches | 1-2 weeks |
| **P1 High** | Revinate RFM Analysis | International | Apply to enterprise card scoring; activate dormant cards (53% zero-output) | 2-4 weeks |
| **P1 High** | Cvent RFP Automation | International | Auto-generate professional MICE proposals from templates + hotel data | 2-4 weeks |
| **P1 High** | Salesforce Guest Journey Orchestration | International | Map to 百达屋 + PMS data integration; build guest journey Skill | 1-2 months |
| **P2 Medium** | Cloudbeds Unified Guest Profiles | International | Profile hygiene automation; duplicate merging; trigger-based campaigns | 1-2 months |
| **P2 Medium** | 纷享销客 9-Dimension CRM | China | Architecture reference for building Chinese-market sales Skill | 1-2 months |
| **P2 Medium** | 新质生产力 Classification | China/Govt | Use as enterprise client segmentation dimension; narrative for SOE pitches | Ongoing |
| **P2 Medium** | PriceLabs MICE Pricing | International | Integrate with hotel-rev-ai for displacement analysis | 2-3 months |
| **P3 Low** | 迈点 Brand Index | China | Strategic context for competitive positioning | Reference only |
| **P3 Low** | D-EDGE CRM | Europe | Pre/in/post-stay communication patterns for MICE | Reference only |

---

## Part 4: Key Recommendations

### 4.1 Immediate Actions (This Week - 5月收官冲刺)

1. **Build a MEDDPICC Sales Qualification Skill** using the SKILL工厂's PLAN/BUILD/EVAL framework:
   - Layer 1 (PLAN): Research the top 20 enterprise card targets, map their decision makers
   - Layer 2 (BUILD): Generate qualification checklists and talk tracks for each
   - Layer 3 (EVAL): Test against the existing 98.8% quality benchmark

2. **Apply MICE Lifecycle Framework** to the 中国智慧会展集团 opportunity:
   - Prepare tiered MICE packages (Standard/VIP/Executive)
   - Include "curated downtime" differentiators (深海温泉SPA, 杭帮菜/江西菜)
   - Create a proposal template Skill that auto-generates MICE proposals

3. **Activate Challenger Sale approach** for all enterprise outreach:
   - Lead with the insight: "AI-empowered hotels reduce total travel cost by X%"
   - Use 德胧AI capabilities as the teaching hook
   - Position Tianjin Ruiwan as a 新质生产力-empowered hospitality partner

### 4.2 Medium-Term (1-2 Months)

4. **Build a Hotel Sales CRM Skill** combining:
   - Revinate's RFM analysis for enterprise card scoring
   - MEDDPICC qualification for pipeline management
   - Cloudbeds' unified guest profile concept
   - 纷享销客's Chinese enterprise sales patterns
   - Integration with `hotel-outreach-tracker` and `hotel-dormant-activator`

5. **Create MICE Proposal Generator** combining:
   - Cvent's RFP automation patterns
   - Thynk.Cloud's tiered packaging framework
   - Hotel-specific data (meeting rooms, catering, room blocks)
   - Auto-generation of professional PDF proposals

### 4.3 Strategic (3-6 Months)

6. **Integrate 新质生产力 narrative** into all external communications:
   - SEO/GEO content should target "新质生产力酒店" keywords
   - Enterprise pitch decks should frame Delonix AI as 新质生产力 in hospitality
   - Government/SOE clients specifically targeted with this narrative

7. **Upgrade SKILL工厂 to v4.0** with:
   - Sales methodology knowledge base (MEDDIC, SPIN, Challenger embedded)
   - MICE-specific Skill generation templates
   - Integration with the hotel-client-dev Skill (enterprise scoring + development work orders)

---

## Part 5: Data Sources Summary

### Feishu Bitable Records Analyzed
- **工具目录总览 (Tool Catalog):** 42 records, 2 directly related to hotel-skill-forge
- **技能工具库 (Skills Library):** 70+ records, SKILL工厂 is infrastructure (no direct install package)
- **经验思路库 (Experience Library):** 25+ records, 2 critical records on SKILL工厂 v3.1 architecture and Eval quality framework

### Web Research Sources
- 6 international sales methodology sources (Salesforce, Cloudbeds, Revinate, Cvent, Thynk.Cloud, PriceLabs)
- 3 B2B playbook sources (MEDDPICC, SPIN, Challenger Sale comparisons)
- 6 Chinese industry sources (迈点, KPMG, 中国饭店协会, 纷享销客, 国家统计局, 国家发改委)
- 4 deep-dive page analyses conducted

---

*Report compiled by AI research agent. All Feishu Bitable data sourced from shared pool ZJ8obBGrSaO9rjsXPvhc1TdYngd.*
