package service

import (
	"context"

	aiprovider "github.com/1024XEngineer/Holonic-Asset/internal/ai/provider"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/domain"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/dto"
)

// ImageProvider is the subset of the AI provider port consumed by generation.
type ImageProvider interface {
	GenerateImage(ctx context.Context, request *aiprovider.ImageGenerationRequest) (*aiprovider.GenerationResult, error)
	EditImage(ctx context.Context, request *aiprovider.ImageEditRequest) (*aiprovider.GenerationResult, error)
}

// GenerateService defines synchronous image generation and editing.
type GenerateService interface {
	GenerateImage(ctx context.Context, request *dto.GenerateImageRequest) (*dto.ImageResult, error)
	EditImage(ctx context.Context, request *dto.EditImageRequest) (*dto.ImageResult, error)
}

type generateService struct {
	provider   ImageProvider
	model      string
	strategies map[domain.GenerationKind]generationStrategy
}

// NewGenerateService creates the internal image generation service.
func NewGenerateService(imageProvider ImageProvider, model string, tools map[domain.GenerationKind][]ImageTool) GenerateService {
	return &generateService{provider: imageProvider, model: model, strategies: newStrategies(tools)}
}

func (s *generateService) GenerateImage(ctx context.Context, request *dto.GenerateImageRequest) (*dto.ImageResult, error) {
	strategy, err := s.strategyFor(request.Kind)
	if err != nil {
		return nil, err
	}
	providerRequest, err := strategy.prepareGenerate(request, s.model)
	if err != nil {
		return nil, err
	}
	result, err := s.provider.GenerateImage(ctx, providerRequest)
	if err != nil {
		return nil, err
	}
	return strategy.process(ctx, result)
}

func (s *generateService) EditImage(ctx context.Context, request *dto.EditImageRequest) (*dto.ImageResult, error) {
	strategy, err := s.strategyFor(request.Kind)
	if err != nil {
		return nil, err
	}
	providerRequest, err := strategy.prepareEdit(request, s.model)
	if err != nil {
		return nil, err
	}
	result, err := s.provider.EditImage(ctx, providerRequest)
	if err != nil {
		return nil, err
	}
	return strategy.process(ctx, result)
}

var _ GenerateService = (*generateService)(nil)
