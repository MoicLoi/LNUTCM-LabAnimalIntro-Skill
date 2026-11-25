# LNUTCM Lab Animal Intro Skill

这个仓库发布 **photo-book-to-ebook** 技能包：把《实验动物学导论》的 320 张手机照片转成可校对、可出版级排版的电子书（Markdown / HTML / EPUB）。

- 技能入口：[SKILL.md](SKILL.md)
- 技能说明：[SKILL-README.md](SKILL-README.md)
- 项目记录：[PROJECT.md](PROJECT.md)
- 软件产品：[MoicLoi/deepseek-web-mobile](https://github.com/MoicLoi/deepseek-web-mobile)

## 为什么单独发布技能

电子书的转写、页码核对、表格网格、补拍、diff 校订和 EPUB 组装是一套独立于客户端的工作流。软件是这套技能的**分支产品**：它消费技能产出的 `book.md` 和附录七例题，做成查阅/出题/片段练习/模拟练习四种复习模式。

## 技能能做什么

- 320 张照片 → 321 页逐页转写，带 `<!-- page: N -->` 页码锚点
- 页码连续性、重复页、空页、表格合并单元格、标签平衡的自动 QC
- 旋转/裁切/增强后的补拍循环
- `<del>`/`<ins>` 与事实核查分离的校订标记
- 无第三方依赖的 Markdown / HTML / EPUB3 构建

## 安装

把整个目录放到 harness 的 skills 目录，或让 agent 直接读取 `SKILL.md`：

```text
~/.workbuddy/skills/photo-book-to-ebook/
~/.claude/skills/photo-book-to-ebook/
```

## 目录

```text
SKILL.md                  # 入口：流程、六条硬规则、失败模式
skill.json                # 可移植清单
SKILL-README.md           # 技能自身说明
PROJECT.md                # LNUTCM《实验动物学导论》项目记录
references/               # 转写规则、QC 清单、目录约定
scripts/                  # init / prep / qc / build
LICENSE                   # MIT
```

## 版权

技能代码 MIT。书中内容版权归原权利人；本仓库不重新分发电子书全文，只发布制作技能与项目记录。
