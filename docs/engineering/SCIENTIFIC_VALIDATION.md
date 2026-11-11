# 科研计算可靠性与物理模型验证基线
## Scientific Validation & Physical Consistency

---

## 一、物理模型与仿真流程基准

本工程涉及有机光伏（OSC）活性层高分子给体（PM6）与小分子受体（FClFCl / ClFFCl 等）的溶液-薄膜自组装全流程分子动力学计算。

### 标准科研模拟链条

```text
EM-1 (最速下降, emtol=1000) 
  ↓
EM-2 (共轭梯度, emtol=100) 
  ↓
NPT-1 (1 ns @ 100 bar, 300 K 快速压紧) 
  ↓
NPT-2 (2 ns @ 1 bar, 300 K 密度稳定) 
  ↓
SA 溶剂分批蒸发 (循环删除 CF 溶剂，逐轮 100 ps NPT 平衡，盒从 ~19.7 nm 缩至 ~10.0 nm)
  ↓
成膜长程平衡 (80 ns 致密无溶剂膜) 
  ↓
剔除添加剂 (一次性删除 94 个 DIO + 1 ns NPT 平衡) 
  ↓
热退火 TA (1.1 ns, 300 K → 373 K → 300 K) 
  ↓
生产动力学平衡 (70 ns, 取末段轨迹用于后处理分析)
```

---

## 二、SA 溶剂蒸发逐轮结构继承法则（PR #1 核心基线）

### 1. 结构与动力学量继承铁律
- **第 $i$ 轮输入结构**：必须严格等于第 $i-1$ 轮成功完成的 `mdrun` 输出结构 `${PREFIX}_${i-1}.gro`（第 1 轮使用初始 `NPT2` 结构）；
- **物理量继承**：
  - 原子坐标与微观收缩盒子从上轮输出传递；
  - 速度信息必须从输入 `.gro` 读取（对应 MDP 中 `continuation = yes` 与 `gen_vel = no`），不得重新生成随机麦克斯韦分布速度；
- **Checkpoint 隔离规则**：
  - 删除溶剂导致体系原子数减少，跨轮复用旧 `.cpt` 属物理严重错误，必须禁止；
  - 仅在第 $N$ 轮自身中途中断时，允许使用本轮的 `${PREFIX}_N.cpt` 恢复动力学校验。

---

## 三、五套 PM6/受体体系 SA 参数对照与科学适用性

| 体系名称 | 受体特征 | 流程脚本 / 目录 | 单轮平衡时长 | 循环轮数与单轮删除量 | 蒸发总时长 | 控压算法与目标压力 | 适用场景与科学依据 |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| **01. PM6 : HDO-4Cl** | 母体对照 (4Cl 对称) | `Ternary_Datas` / `npt_1.sge` | **100 ps** | 250 轮 × 200 个 CF | **25 ns** | Berendsen (100 bar, $\tau_p=0.5$) | 原始发表标准协议，由疏松大盒压实 |
| **02. PM6 : BTP-FClClF** | 对称异卤 (F-Cl-Cl-F) | `Ternary_Datas` / `npt_1.sge` | **100 ps** | 250 轮 × 200 个 CF | **25 ns** | Berendsen (100 bar, $\tau_p=0.5$) | 严格对齐母体对照实验成膜时间尺度 |
| **03. PM6 : BTP-ClFFCl** | 对称异卤 (Cl-F-F-Cl) | `examples/ClFFCl/ydw-npt-sa.mdp` | **10 ps** | 500 轮 × 100 个 CF | **5 ns** | Parrinello-Rahman (1 bar, $\tau_p=1.0$) | **快速原型探索**：步长放宽至 2 fs，快速摸底 |
| **04. PM6 : BTP-FClFCl** | 非对称异卤 (F-Cl-F-Cl) | `examples/FClFCl/ydw-npt-remove.mdp` | **100 ps** | 500 轮 × 100 个 CF | **50 ns** | Parrinello-Rahman (1 bar, $\tau_p=1.0$) | **精细自组装**：单轮删除量减半，总松弛 50 ns 充分重排 |
| **05. PM6 : BTP-FFClCl** | 非对称异卤 (F-F-Cl-Cl) | `Ternary_Datas` / `MD-4-BT4` | **100 ps** | 250 轮 × 200 个 CF | **25 ns** | Berendsen (100 bar, $\tau_p=0.5$) | 遵循 250 轮标准协议 |

> **重要准则**：严禁在代码中强行统一各体系参数；各体系的科学配置由其研究目的与实验对应物决定。
