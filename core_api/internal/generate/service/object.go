package service

type objectStrategy struct {
	baseGenerationStrategy
}

func newObjectStrategy(tools []ImageTool) generationStrategy {
	return &objectStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}
