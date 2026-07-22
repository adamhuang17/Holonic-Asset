package handler

import (
	"github.com/labstack/echo/v4"

	"github.com/1024XEngineer/Holonic-Asset/internal/asset/dto"
	"github.com/1024XEngineer/Holonic-Asset/internal/asset/service"
)

type Handler struct {
	AssetService         service.AssetService
	AssetResourceService service.AssetResourceService
	AssetVerionService   service.AssetVersionService
}

func NewHandler(as service.AssetService, rs service.AssetResourceService, vs service.AssetVersionService) *Handler {
	return &Handler{
		AssetService:         as,
		AssetResourceService: rs,
		AssetVerionService:   vs,
	}
}

func (h *Handler) GetAssets(x echo.Context) ([]dto.GetAssetsResponse, error) {
	ctx := x.Request().Context()
	_, err := h.AssetService.GetAssets(ctx, 1)
	return nil, err
}

func (h *Handler) Detail(x echo.Context) (dto.AssetDetailResponse, error) {
	return dto.AssetDetailResponse{}, nil
}

func (h *Handler) Record(x echo.Context, asset dto.RecordAssetRequest) ([]dto.RecordAssetResponse, error) {
	return []dto.RecordAssetResponse{}, nil
}

func (h *Handler) CreateCharacterAsset(ctx echo.Context, asset dto.CreateCharacterAssetRequest) (dto.CreateCharacterAssetResponse, error) {
	return dto.CreateCharacterAssetResponse{}, nil
}

func (h *Handler) CreateObjectAsset(ctx echo.Context, asset dto.CreateObjectAssetRequest) (dto.CreateObjectAssetResponse, error) {
	return dto.CreateObjectAssetResponse{}, nil
}

func (h *Handler) CreateTileSetAsset(ctx echo.Context, asset dto.CreateTileSetAssetRequest) (dto.CreateTileSetAssetResponse, error) {
	return dto.CreateTileSetAssetResponse{}, nil
}

func (h *Handler) CopyAsset(ctx echo.Context, asset dto.CopyAssetRequest) (dto.CopyAssetResponse, error) {
	return dto.CopyAssetResponse{}, nil
}

func (h *Handler) Tags(ctx echo.Context, req dto.AddTagsRequest) (dto.AddTagsResponse, error) {
	return dto.AddTagsResponse{}, nil
}
