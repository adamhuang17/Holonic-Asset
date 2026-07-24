package service

import (
	"context"
	"errors"
	"strings"

	aiprovider "github.com/1024XEngineer/Holonic-Asset/internal/ai/provider"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/domain"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/dto"
)

// ImageTool applies one kind-specific image processing step.
//
// specification carries the kind-specific domain Specification assembled for the
// request (e.g. domain.TileSetSpecification, domain.AnimationSpecification), or
// nil when the request has no specification. The tool list is already keyed by
// generation kind, so a tool may safely type-assert to the specification it
// expects for its own kind.
type ImageTool interface {
	Process(ctx context.Context, imageURLs []string, specification any) ([]string, error)
}

type generationStrategy interface {
	executeGenerate(
		ctx context.Context,
		provider ImageProvider,
		requestID string,
		model string,
		input generationInput,
	) (*aiprovider.GenerationResult, error)
	executeEdit(
		ctx context.Context,
		provider ImageProvider,
		requestID string,
		model string,
		input editInput,
	) (*aiprovider.GenerationResult, error)
	processGenerate(
		ctx context.Context,
		input generationInput,
		result *aiprovider.GenerationResult,
	) (*dto.ImageResult, error)
	processEdit(
		ctx context.Context,
		input editInput,
		result *aiprovider.GenerationResult,
	) (*dto.ImageResult, error)
}

type baseGenerationStrategy struct {
	tools []ImageTool
}

type generationInput struct {
	promptParts   []string
	references    []domain.ImageReference
	size          domain.Size
	specification any
}

type editInput struct {
	promptParts []string
	target      domain.ImageReference
}

var (
	errImageResultRequired       = errors.New("image provider returned no image")
	errGenerationKindUnsupported = errors.New("unsupported generation kind")
)

func assembleGenerationInput(generationContext domain.GenerationContext) generationInput {
	return generationInput{
		promptParts: []string{
			generationContext.Project.Style,
			generationContext.Asset.Description,
			generationContext.Description,
		},
		references: append([]domain.ImageReference(nil), generationContext.References...),
		size:       generationContext.Size,
	}
}

func assembleTargetEdit(
	plan domain.EditPlan,
	target domain.ImageReference,
	targetEdit domain.TargetEdit,
) editInput {
	return editInput{
		promptParts: []string{
			plan.StyleDescription,
			plan.SharedDescription,
			targetEdit.Description,
		},
		target: target,
	}
}

func (s *baseGenerationStrategy) executeGenerate(
	ctx context.Context,
	provider ImageProvider,
	requestID string,
	model string,
	input generationInput,
) (*aiprovider.GenerationResult, error) {
	return provider.GenerateImage(ctx, buildGenerationRequest(requestID, model, input))
}

func (s *baseGenerationStrategy) executeEdit(
	ctx context.Context,
	provider ImageProvider,
	requestID string,
	model string,
	input editInput,
) (*aiprovider.GenerationResult, error) {
	return provider.EditImage(ctx, buildEditRequest(requestID, model, input))
}

func buildGenerationRequest(
	requestID string,
	model string,
	input generationInput,
) *aiprovider.ImageGenerationRequest {
	return &aiprovider.ImageGenerationRequest{
		RequestID: requestID,
		Model:     model,
		ImageGenerationInput: aiprovider.ImageGenerationInput{
			Prompt:        buildPrompt(input.promptParts...),
			ReferenceURLs: referenceURLs(input.references),
			Size: aiprovider.Size{
				Width:  input.size.Width,
				Height: input.size.Height,
			},
		},
	}
}

func buildEditRequest(
	requestID string,
	model string,
	input editInput,
) *aiprovider.ImageEditRequest {
	return &aiprovider.ImageEditRequest{
		RequestID:  requestID,
		Model:      model,
		Prompt:     buildPrompt(input.promptParts...),
		TargetURLs: []string{input.target.URL},
	}
}

func (s *baseGenerationStrategy) processGenerate(
	ctx context.Context,
	input generationInput,
	result *aiprovider.GenerationResult,
) (*dto.ImageResult, error) {
	return s.runTools(ctx, result, input.specification)
}

func (s *baseGenerationStrategy) processEdit(
	ctx context.Context,
	input editInput,
	result *aiprovider.GenerationResult,
) (*dto.ImageResult, error) {
	return s.runTools(ctx, result, nil)
}

// runTools threads the assembled specification through the post-processing
// pipeline so that each tool can see the Specification that produced the images,
// not just the resulting URLs.
func (s *baseGenerationStrategy) runTools(
	ctx context.Context,
	result *aiprovider.GenerationResult,
	specification any,
) (*dto.ImageResult, error) {
	if result == nil || len(result.OutputURLs) == 0 {
		if result != nil && result.ErrorMessage != "" {
			return nil, errors.New(result.ErrorMessage)
		}
		return nil, errImageResultRequired
	}
	outputURLs := result.OutputURLs
	for _, tool := range s.tools {
		var err error
		outputURLs, err = tool.Process(ctx, outputURLs, specification)
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

func buildPrompt(descriptions ...string) string {
	parts := make([]string, 0, len(descriptions))
	for _, description := range descriptions {
		if description != "" {
			parts = append(parts, description)
		}
	}
	return strings.Join(parts, "\n")
}

func referenceURLs(references []domain.ImageReference) []string {
	urls := make([]string, 0, len(references))
	for _, reference := range references {
		urls = append(urls, reference.URL)
	}
	return urls
}

func (s *generateService) strategyFor(kind domain.GenerationKind) (generationStrategy, error) {
	strategy, ok := s.strategies[kind]
	if !ok {
		return nil, errGenerationKindUnsupported
	}
	return strategy, nil
}
