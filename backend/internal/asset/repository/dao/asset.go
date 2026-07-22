package dao

import (
	"context"
	"encoding/json"
)

type Asset struct {
	ID          uint
	Name        string
	ProjectID   uint
	Type        string
	Description string
	Tags        []string        `json:"tags"`
	Attributes  json.RawMessage `json:"attributes"`
	Version     uint
}

type AssetDao interface {
	CreateAsset(ctx context.Context, asset *Asset) (uint, error)
}
