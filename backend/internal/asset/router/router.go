package router

import (
	"github.com/labstack/echo/v4"

	"github.com/1024XEngineer/Holonic-Asset/internal/asset/dto"
	"github.com/1024XEngineer/Holonic-Asset/pkg/echox"
)

type AssetRouter interface {
	GetAssets(x echo.Context) ([]dto.GetAssetsResponse, error)
	Detail(x echo.Context) (dto.AssetDetailResponse, error)
	Record(x echo.Context, req dto.RecordAssetRequest) ([]dto.RecordAssetResponse, error)
	CreateCharacterAsset(ctx echo.Context, req dto.CreateCharacterAssetRequest) (dto.CreateCharacterAssetResponse, error)
	CreateObjectAsset(ctx echo.Context, req dto.CreateObjectAssetRequest) (dto.CreateObjectAssetResponse, error)
	CreateTileSetAsset(ctx echo.Context, req dto.CreateTileSetAssetRequest) (dto.CreateTileSetAssetResponse, error)
	CopyAsset(ctx echo.Context, req dto.CopyAssetRequest) (dto.CopyAssetResponse, error)

	Tags(ctx echo.Context, req dto.AddTagsRequest) (dto.AddTagsResponse, error)
}

// RegisterRoutes registers all HTTP routes.
func RegisterRoutes(e *echo.Group, r AssetRouter) {
	project := e.Group("/projects")

	project.GET("/:project_id/assets", echox.Wrap(r.GetAssets))

	asset := e.Group("/asset")

	asset.GET("/:asset_id", echox.Wrap(r.Detail))

	asset.POST("/save", echox.WrapReq(r.Record))

	asset.POST("/characters", echox.WrapReq(r.CreateCharacterAsset))

	asset.POST("/objects", echox.WrapReq(r.CreateObjectAsset))

	asset.POST("/tilesets", echox.WrapReq(r.CreateTileSetAsset))

	asset.POST("/copy", echox.WrapReq(r.CopyAsset))

	asset.POST("/tags", echox.WrapReq(r.Tags))
}
