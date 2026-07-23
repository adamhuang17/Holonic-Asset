package service

type uiStrategy struct {
	baseGenerationStrategy
}

func newUIStrategy(tools []ImageTool) generationStrategy {
	return &uiStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}
