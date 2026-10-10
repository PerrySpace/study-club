"""路由层（View）：只做参数解析 / 鉴权依赖 / 响应信封（06-1 §3.1）。

分层纪律：views 只声明 `repos: Repositories = Depends(get_repos)`，
业务逻辑一律在 `controllers/`，数据访问一律在 `repositories/`。

⛔ 掩藏能力（手机号/微信账号、短信 OTP、支付、推送、多角色 RBAC）在此**不注册任何路由**，
即使前端被绕过也调不到。
"""
