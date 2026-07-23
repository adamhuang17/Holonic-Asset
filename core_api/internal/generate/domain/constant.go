package domain

// GenerationKind identifies the asset-oriented generation capability.
type GenerationKind string

const (
	GenerationKindImage     GenerationKind = "image"
	GenerationKindCharacter GenerationKind = "character"
	GenerationKindTileSet   GenerationKind = "tileSet"
	GenerationKindObject    GenerationKind = "object"
	GenerationKindScenery   GenerationKind = "scenery"
	GenerationKindAnimation GenerationKind = "animation"
	GenerationKindUI        GenerationKind = "ui"
)
