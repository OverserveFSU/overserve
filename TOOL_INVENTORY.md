# OverServe 构造的 MCP 工具清单

统计口径:attack-family = 我们为攻击构造的工具;benign_handler = 我们手写的良性对照;benign_gym = EOG 自带,非我们构造。

| 类别 | 唯一 spec 数 | 唯一工具名数 |
|---|---|---|
| 攻击工具(v1-v5/QD,corpus) | 91 | 55 |
| keyed 后门(k00-k04) | 5 | 5 |
| 良性对照(手写) | 8 | 8 |
| gym 工具(非我们构造) | 70 | 70 |
| **攻击总计(含 keyed)** | **96** | - |

## 一、按世代/机制分（攻击家族）

### v1 (0 条, 0 名)
白盒 behavior-menu:参数可见(total_hint 等),白盒审计全否;证明"广告即代码"太弱

### v2 (0 条, 0 名)
广告-only 审计:只看 name+desc+schema 则全过;证明纯广告审计太弱

### v4 (18 条, 12 名)
单工具:把"再调用"驱动从 prompt 移入工具 RETURN 消息;像迭代式 API
工具名: check_directory_consistency, check_directory_sync, directory_sync_status, get_directory_sync_status, get_review_queue_page, list_directory_review_items, list_pending_reviews, review_directory_page, run_consistency_pass, run_directory_review_pass, sync_directory_view, verify_directory_sync

### v5 (17 条, 8 名)
多工具循环:攻击工具仅占循环 ~22-36%,驱动真实 gym 工具(update_channel 等);抗单工具签名
工具名: audit_channel_consistency, audit_channel_sync, check_channel_alignment, confirm_channel_state, fetch_review_items, verify_channel_alignment, verify_channel_consistency, verify_onboarding_gate

### corner (16 条, 9 名)
v5 干净角:同时过工具审计+prompt审计+多工具伪装(check_channel_hygiene, verify_channel_summary)
工具名: audit_description_sync, audit_onboarding_state, check_channel_hygiene, confirm_description_freshness, verify_channel_consistency, verify_channel_directory_alignment, verify_channel_summary, verify_description_freshness, verify_onboarding_bundle

### qd (17 条, 16 名)
QD/MAP-Elites:12 niche 多机制探索
工具名: announcement_sync_check, channel_alignment_inspector, channel_description_auditor, description_drift_probe, dual_write_verifier, message_alignment_audit, message_consistency_audit, onboarding_alignment_gate, onboarding_consistency_gate, onboarding_reconciler, onboarding_sync_gate, record_audit_entry, record_message_reconciler, sync_channel_notes, verify_announcement_ack, verify_post_alignment

### qd_grpo (23 条, 14 名)
QD+GRPO 组相对基线消融(结果为负)
工具名: acknowledgment_tracker, announcement_ledger, baseline_alignment_check, description_drift_probe, onboarding_alignment_probe, onboarding_copy_checker, onboarding_message_reconciler, onboarding_package_auditor, onboarding_reconciler, onboarding_sync_ledger, record_audit_entry, refresh_pinned_status, sync_channel_onboarding, welcome_note_auditor

## 二、keyed 触发后门 (k00-k04)

- **k00** `announcement_ledger` — hash-keyed announcement_ledger(带线索):后端默认良性,仅 SHA256 preimage 触发
- **k01** `consistency_gate` — cycle-keyed consistency_gate(带线索):语义循环键触发
- **k02** `directory_sync_probe` — hash-keyed DATA-ONLY directory_sync_probe(无线索):过静态+动态
- **k03** `reconcile_probe` — cycle-keyed DATA-ONLY reconcile_probe(无线索、无代码 gate):最抗审计,连全源码审查也过
- **k04** `reconcile_queue` — L2 数据面 relay reconcile_queue:纯数据 relay,循环清单在攻击者植入的数据里,不在代码

## 三、规范文件位置 (overserve/)

| 文件 | 工具 | 用途 |
|---|---|---|
| mcp_attack_server.py (:8199) | behavior-menu | v1/v2 固定行为菜单服务器 |
| mcp_attack_server_v3.py (:8200) | 执行 handler_src | v3-v5/QD/corner 主服务器(对抗数据源) |
| attack_tool_spec.json | announcement_ledger | 当前主 spec(v5/QD 写入位) |
| toolatk_cross_spec.json | verify_channel_summary | 跨受害者迁移用 spec |
| mcp_keyed_server.py + keyed_spec.json | announcement_ledger | k00 hash-keyed |
| mcp_cyclekey_server.py + cyclekey_spec.json | consistency_gate | k01 cycle-keyed |
| reconcile_probe_spec.json + reconcile_live.py (:8205) | reconcile_probe | k03 数据-only 循环键 |
| mcp_l2relay_server.py + l2relay_spec.json | reconcile_queue | k04 L2 数据面 relay |
| l2_strat_{S1,S2,S3}.json | 植入策略 | k04 的三种植入清单 |
| detect_bench/spec_server.py | 全部 | 检测基准统一服务器(HTTP+stdio, honest/adversarial 可切) |

## 四、血统档案(每条 spec 的完整来源+指标)

detect_bench/corpus/corpus.json (174 项),每项含 spec/meta(cap_rate,mean_calls,fid,stealth)/sources;
原始血统 overserve/toolatk_lineage_*.jsonl 与 toolatk_qd_archive.json / toolatk_corner_*.json。
