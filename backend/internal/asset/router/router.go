package router

import (
	"context"

	"github.com/labstack/echo/v4"

	"github.com/1024XEngineer/Holonic-Asset/pkg/echox"
)

type AssetRouter interface {
	GetAssets(x echo.Context, request GetAssetsRequest) ([]GetAssetsResponse, error)
	Detail(x echo.Context, assetID uint) (*AssetDetailResponse, error)
	Record(x echo.Context, asset RecordAssetRequest) ([]RecordAssetResponse, error)
	CreateCharacterAsset(ctx echo.Context, asset CreateCharacterAssetRequest) (CreateCharacterAssetResponse, error)
	CreateObjectAsset(ctx echo.Context, asset CreateObjectAssetRequest) (CreateObjectAssetResponse, error)
	CreateTileSetAsset(ctx echo.Context, asset CreateTileSetAssetRequest) (CreateTileSetAssetResponse, error)
	CopyAsset(ctx echo.Context, asset CopyAssetRequest) (CopyAssetResponse, error)

	Tags(ctx echo.Context, assetID uint, tags []string)error
}


// registerRoutes 注册所有 HTTP 路由。
func RegisterRoutes(e *echo.Group, r AssetRouter) {
	asset:=e.Group("/asset")
	asset.GET("/health", echox.WrapReq(r.GetAssets))
}