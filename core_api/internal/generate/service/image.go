package service

type imageStrategy struct {
	baseGenerationStrategy
}

func newImageStrategy(tools []ImageTool) generationStrategy {
	return &imageStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}
