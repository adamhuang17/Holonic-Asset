package domain

type Size struct {
	Width  uint
	Height uint
}

type ProjectContext struct {
	Style string
}

type AssetContext struct {
	Description string
}

type ImageReference struct {
	URL string
}

type GenerationContext struct {
	Project     ProjectContext
	Asset       AssetContext
	Description string
	References  []ImageReference
	Size        Size
}

type EditContext struct {
	Project     ProjectContext
	Asset       AssetContext
	Instruction string
	Targets     []ImageReference
}

type TargetEdit struct {
	TargetIndex int
	Description string
}

type EditPlan struct {
	StyleDescription  string
	SharedDescription string
	Targets           []TargetEdit
}

type AnimationSpecification struct {
	Prototype  ImageReference
	FrameCount uint
	Loop       bool
}

type TileSetItem struct {
	Name        string
	Description string
	References  []ImageReference
	SpanColumns uint
	SpanRows    uint
}

type TileSetSpecification struct {
	GridSize Size
	Item     TileSetItem
}
