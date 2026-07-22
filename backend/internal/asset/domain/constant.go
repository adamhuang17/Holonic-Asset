package domain

type AssetType string
type AssetResourceType string
type Status uint


const (

AssetTypeCharacter AssetType = "character"

AssetTypeTileSet AssetType = "tileSet"

AssetTypeAudio AssetType = "audio"

AssetTypeUI AssetType = "ui"

AssetTypeObject AssetType = "object"

AssetTypeScenery AssetType = "scenery"

)

const (

AssetResourceTypeProtoType AssetResourceType = "protoType"

// image绑定在protoType上
AssetResourceTypeImage     AssetResourceType = "image"

AssetResourceTypeAnimation AssetResourceType = "animation"

// frame绑定在animation上
AssetResourceTypeFrame AssetResourceType = "frame"

AssetResourceTypeItem AssetResourceType = "item"

// tile绑定在item上
AssetResourceTypeTile AssetResourceType = "tile"

AssetResourceTypeUI AssetResourceType = "ui"

AssetResourceTypeScenery AssetResourceType = "scenery"

)

const (
	StatusPending Status = iota
	StatusProcessing
	StatusCompleted
	StatusFailed
)
