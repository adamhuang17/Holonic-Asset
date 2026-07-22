package router

import (
	"github.com/1024XEngineer/Holonic-Asset/internal/asset/domain"
)

type GetAssetsRequest struct {
	ProjectID uint
}

type GetAssetsResponse struct {
	AssetID     uint
	Name        string
	ProjectID   uint
	Type        domain.AssetType
	Description string
	Tags        []string
	Version     uint
}

type AssetDetailResponse struct {
}

type CreateCharacterAssetRequest struct {
	Asset *domain.Asset
}

type CreateCharacterAssetResponse struct {
	ID uint
}

type CreateObjectAssetRequest struct {
	Asset *domain.Asset
}

type CreateObjectAssetResponse struct {
	ID uint
}

type CreateTileSetAssetRequest struct {
	Asset *domain.Asset
}

type CreateTileSetAssetResponse struct {
	ID uint
}

type RecordAssetRequest struct {
}

type RecordAssetResponse struct {
}

type CopyAssetRequest struct {
	AssetID uint
}

type CopyAssetResponse struct {
	NewAssetID uint
}
