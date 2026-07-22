package internal

import (
	"github.com/labstack/echo/v4"

	asset "github.com/1024XEngineer/Holonic-Asset/internal/asset/router"
)

// Register assembles and returns all routes.
func Register(as asset.AssetRouter) *echo.Echo {
	e := echo.New()
	api := e.Group("/api/v1")
	asset.RegisterRoutes(api, as)

	return e
}
