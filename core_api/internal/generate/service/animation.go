package service

import (
	"fmt"

	"github.com/1024XEngineer/Holonic-Asset/internal/generate/domain"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/dto"
)

type animationStrategy struct {
	baseGenerationStrategy
}

func newAnimationStrategy(tools []ImageTool) generationStrategy {
	return &animationStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}

func assembleAnimationInput(request *dto.GenerateAnimationRequest) generationInput {
	input := assembleGenerationInput(request.Context)
	specification := request.Specification
	input.specification = specification
	input.promptParts = append(
		input.promptParts,
		fmt.Sprintf("Animation frame count: %d", specification.FrameCount),
		fmt.Sprintf("Animation loop: %t", specification.Loop),
	)
	input.references = append(
		[]domain.ImageReference{specification.Prototype},
		input.references...,
	)
	return input
}
