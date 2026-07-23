package service

type tileSetStrategy struct {
	baseGenerationStrategy
}

func newTileSetStrategy(tools []ImageTool) generationStrategy {
	return &tileSetStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}
