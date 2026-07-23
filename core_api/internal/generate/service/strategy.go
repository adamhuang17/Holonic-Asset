package service

import (
	"context"
	"errors"

	aiprovider "github.com/1024XEngineer/Holonic-Asset/internal/ai/provider"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/domain"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/dto"
)

// ImageTool applies one kind-specific image processing step.
type ImageTool interface {
	Process(ctx context.Context, imageURLs []string) ([]string, error)
}

type generationStrategy interface {
	prepareGenerate(request *dto.GenerateImageRequest, model string) (*aiprovider.ImageGenerationRequest, error)
	prepareEdit(request *dto.EditImageRequest, model string) (*aiprovider.ImageEditRequest, error)
	process(ctx context.Context, result *aiprovider.GenerationResult) (*dto.ImageResult, error)
}

type baseGenerationStrategy struct {
	tools []ImageTool
}

var (
	errImageResultRequired       = errors.New("image provider returned no image")
	errGenerationKindUnsupported = errors.New("unsupported generation kind")
)

func (s *baseGenerationStrategy) prepareGenerate(request *dto.GenerateImageRequest, model string) (*aiprovider.ImageGenerationRequest, error) {
	return &aiprovider.ImageGenerationRequest{
		RequestID: request.RequestID,
		Model:     model,
		ImageGenerationInput: aiprovider.ImageGenerationInput{
			Prompt:        request.Prompt,
			ReferenceURLs: request.ReferenceURLs,
			Size: aiprovider.Size{
				Width:  request.Size.Width,
				Height: request.Size.Height,
			},
		},
	}, nil
}

func (s *baseGenerationStrategy) prepareEdit(request *dto.EditImageRequest, model string) (*aiprovider.ImageEditRequest, error) {
	return &aiprovider.ImageEditRequest{
		RequestID:  request.RequestID,
		Model:      model,
		Prompt:     request.Prompt,
		TargetURLs: request.TargetURLs,
	}, nil
}

func (s *baseGenerationStrategy) process(ctx context.Context, result *aiprovider.GenerationResult) (*dto.ImageResult, error) {
	if result == nil || len(result.OutputURLs) == 0 {
		if result != nil && result.ErrorMessage != "" {
			return nil, errors.New(result.ErrorMessage)
		}
		return nil, errImageResultRequired
	}
	outputURLs := result.OutputURLs
	for _, tool := range s.tools {
		var err error
		outputURLs, err = tool.Process(ctx, outputURLs)
		if err != nil {
			return nil, err
		}
		if len(outputURLs) == 0 {
			return nil, errImageResultRequired
		}
	}
	return &dto.ImageResult{OutputURLs: outputURLs}, nil
}

func newStrategies(tools map[domain.GenerationKind][]ImageTool) map[domain.GenerationKind]generationStrategy {
	return map[domain.GenerationKind]generationStrategy{
		domain.GenerationKindImage:     newImageStrategy(toolsFor(tools, domain.GenerationKindImage)),
		domain.GenerationKindCharacter: newCharacterStrategy(toolsFor(tools, domain.GenerationKindCharacter)),
		domain.GenerationKindTileSet:   newTileSetStrategy(toolsFor(tools, domain.GenerationKindTileSet)),
		domain.GenerationKindObject:    newObjectStrategy(toolsFor(tools, domain.GenerationKindObject)),
		domain.GenerationKindScenery:   newSceneryStrategy(toolsFor(tools, domain.GenerationKindScenery)),
		domain.GenerationKindAnimation: newAnimationStrategy(toolsFor(tools, domain.GenerationKindAnimation)),
		domain.GenerationKindUI:        newUIStrategy(toolsFor(tools, domain.GenerationKindUI)),
	}
}

func toolsFor(tools map[domain.GenerationKind][]ImageTool, kind domain.GenerationKind) []ImageTool {
	return append([]ImageTool(nil), tools[kind]...)
}

func (s *generateService) strategyFor(kind domain.GenerationKind) (generationStrategy, error) {
	strategy, ok := s.strategies[kind]
	if !ok {
		return nil, errGenerationKindUnsupported
	}
	return strategy, nil
}
