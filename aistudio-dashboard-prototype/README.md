# AI Studio 多 Agent 制作流原型

静态单页高保真原型，固定使用 `run23` 的真实产物作为页面素材。

## 运行

在仓库根目录执行：

```bash
python3 -m http.server 8307 -d aistudio-dashboard-prototype
```

浏览器打开：

```text
http://127.0.0.1:8307/
```

## 说明

- 不连接真实后端
- 不读取真实运行状态
- 页面里的流程、审核节点、阻塞原因、事件流全部写死在 `script.js`
- 图片和视频素材来自 `run23` 的真实产物

## 当前原型结构

- `index.html`
  - 单页容器
- `styles.css`
  - 视觉样式与响应式布局
- `script.js`
  - `run23` 的静态项目数据、快照切换与页面交互
- `assets/run23/...`
  - 从 `run23` 拷贝出的角色图、场景图、道具图、参考板、shot video、final video
