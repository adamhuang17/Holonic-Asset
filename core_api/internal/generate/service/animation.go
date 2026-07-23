package service

type animationStrategy struct {
	baseGenerationStrategy
}

func newAnimationStrategy(tools []ImageTool) generationStrategy {
	return &animationStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}
