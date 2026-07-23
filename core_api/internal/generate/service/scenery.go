package service

type sceneryStrategy struct {
	baseGenerationStrategy
}

func newSceneryStrategy(tools []ImageTool) generationStrategy {
	return &sceneryStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}
