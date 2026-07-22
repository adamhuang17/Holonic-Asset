package internal

import (
	"github.com/labstack/echo/v4"

	asset "github.com/1024XEngineer/Holonic-Asset/internal/asset/router"
)

// Register 组装并返回所有路由。
// 当前仅注册 health 端点。
func Register(as asset.AssetRouter) *echo.Echo {
	e := echo.New()
	api := e.Group("/api/v1")
	asset.RegisterRoutes(api,as)

	return e
}