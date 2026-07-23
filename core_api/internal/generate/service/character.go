package service

type characterStrategy struct {
	baseGenerationStrategy
}

func newCharacterStrategy(tools []ImageTool) generationStrategy {
	return &characterStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}
