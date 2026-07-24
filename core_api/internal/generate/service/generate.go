package service

import (
	"context"
	"errors"
	"fmt"

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
	GenerateCharacter(ctx context.Context, request *dto.GenerateCharacterRequest) (*dto.ImageResult, error)
	GenerateTileSet(ctx context.Context, request *dto.GenerateTileSetRequest) (*dto.ImageResult, error)
	GenerateObject(ctx context.Context, request *dto.GenerateObjectRequest) (*dto.ImageResult, error)
	GenerateScenery(ctx context.Context, request *dto.GenerateSceneryRequest) (*dto.ImageResult, error)
	GenerateAnimation(ctx context.Context, request *dto.GenerateAnimationRequest) (*dto.ImageResult, error)
	GenerateUI(ctx context.Context, request *dto.GenerateUIRequest) (*dto.ImageResult, error)
	EditImage(ctx context.Context, request *dto.EditImageRequest) (*dto.EditImageResult, error)
}

type generateService struct {
	provider   ImageProvider
	planner    SemanticPlanner
	model      string
	strategies map[domain.GenerationKind]generationStrategy
}

// NewGenerateService creates the internal image generation service.
func NewGenerateService(imageProvider ImageProvider, model string, tools map[domain.GenerationKind][]ImageTool) GenerateService {
	var planner SemanticPlanner
	if languageProvider, ok := imageProvider.(LanguageProvider); ok {
		planner = NewSemanticPlanner(languageProvider)
	}
	return NewGenerateServiceWithPlanner(imageProvider, planner, model, tools)
}

// NewGenerateServiceWithPlanner allows the semantic planner to be supplied
// independently from the image provider.
func NewGenerateServiceWithPlanner(
	imageProvider ImageProvider,
	planner SemanticPlanner,
	model string,
	tools map[domain.GenerationKind][]ImageTool,
) GenerateService {
	return &generateService{
		provider:   imageProvider,
		planner:    planner,
		model:      model,
		strategies: newStrategies(tools),
	}
}

func (s *generateService) GenerateImage(
	ctx context.Context,
	request *dto.GenerateImageRequest,
) (*dto.ImageResult, error) {
	if request == nil {
		return nil, errGenerationRequestRequired
	}
	return s.generateBase(ctx, domain.GenerationKindImage, request.BaseGenerationRequest)
}

func (s *generateService) GenerateCharacter(
	ctx context.Context,
	request *dto.GenerateCharacterRequest,
) (*dto.ImageResult, error) {
	if request == nil {
		return nil, errGenerationRequestRequired
	}
	return s.generateBase(ctx, domain.GenerationKindCharacter, request.BaseGenerationRequest)
}

func (s *generateService) GenerateTileSet(
	ctx context.Context,
	request *dto.GenerateTileSetRequest,
) (*dto.ImageResult, error) {
	if request == nil {
		return nil, errGenerationRequestRequired
	}
	return s.generate(
		ctx,
		domain.GenerationKindTileSet,
		request.RequestID,
		assembleTileSetInput(request),
	)
}

func (s *generateService) GenerateObject(
	ctx context.Context,
	request *dto.GenerateObjectRequest,
) (*dto.ImageResult, error) {
	if request == nil {
		return nil, errGenerationRequestRequired
	}
	return s.generateBase(ctx, domain.GenerationKindObject, request.BaseGenerationRequest)
}

func (s *generateService) GenerateScenery(
	ctx context.Context,
	request *dto.GenerateSceneryRequest,
) (*dto.ImageResult, error) {
	if request == nil {
		return nil, errGenerationRequestRequired
	}
	return s.generateBase(ctx, domain.GenerationKindScenery, request.BaseGenerationRequest)
}

func (s *generateService) GenerateAnimation(
	ctx context.Context,
	request *dto.GenerateAnimationRequest,
) (*dto.ImageResult, error) {
	if request == nil {
		return nil, errGenerationRequestRequired
	}
	return s.generate(
		ctx,
		domain.GenerationKindAnimation,
		request.RequestID,
		assembleAnimationInput(request),
	)
}

func (s *generateService) GenerateUI(
	ctx context.Context,
	request *dto.GenerateUIRequest,
) (*dto.ImageResult, error) {
	if request == nil {
		return nil, errGenerationRequestRequired
	}
	return s.generateBase(ctx, domain.GenerationKindUI, request.BaseGenerationRequest)
}

func (s *generateService) generateBase(
	ctx context.Context,
	kind domain.GenerationKind,
	request dto.BaseGenerationRequest,
) (*dto.ImageResult, error) {
	return s.generate(ctx, kind, request.RequestID, assembleGenerationInput(request.Context))
}

func (s *generateService) generate(
	ctx context.Context,
	kind domain.GenerationKind,
	requestID string,
	input generationInput,
) (*dto.ImageResult, error) {
	strategy, err := s.strategyFor(kind)
	if err != nil {
		return nil, err
	}
	result, err := strategy.executeGenerate(
		ctx,
		s.provider,
		requestID,
		s.model,
		input,
	)
	if err != nil {
		return nil, err
	}
	return strategy.processGenerate(ctx, input, result)
}

func (s *generateService) EditImage(
	ctx context.Context,
	request *dto.EditImageRequest,
) (*dto.EditImageResult, error) {
	if request == nil {
		return nil, errEditRequestRequired
	}
	strategy, err := s.strategyFor(request.Kind)
	if err != nil {
		return nil, err
	}
	if err := validateEditContext(request.Context); err != nil {
		return nil, err
	}
	if s.planner == nil {
		return nil, errSemanticPlannerRequired
	}

	plan, err := s.planner.PlanEdit(ctx, request.RequestID, s.model, request.Context)
	if err != nil {
		return nil, fmt.Errorf("plan image edits: %w", err)
	}
	if err := validateEditPlan(plan, len(request.Context.Targets)); err != nil {
		return nil, err
	}

	editedImages := make([]dto.EditedImage, len(request.Context.Targets))
	for _, targetEdit := range plan.Targets {
		targetIndex := targetEdit.TargetIndex
		input := assembleTargetEdit(plan, request.Context.Targets[targetIndex], targetEdit)
		result, err := strategy.executeEdit(
			ctx,
			s.provider,
			editTargetRequestID(request.RequestID, targetIndex),
			s.model,
			input,
		)
		if err != nil {
			return nil, fmt.Errorf("edit target %d: %w", targetIndex, err)
		}

		processed, err := strategy.processEdit(ctx, input, result)
		if err != nil {
			return nil, fmt.Errorf("process edited target %d: %w", targetIndex, err)
		}
		if len(processed.OutputURLs) != 1 || processed.OutputURLs[0] == "" {
			return nil, fmt.Errorf(
				"edit target %d: %w: got %d outputs",
				targetIndex,
				errEditedImageCountInvalid,
				len(processed.OutputURLs),
			)
		}
		editedImages[targetIndex] = dto.EditedImage{
			TargetIndex: targetIndex,
			OutputURL:   processed.OutputURLs[0],
		}
	}

	return &dto.EditImageResult{EditedImages: editedImages}, nil
}

var (
	errGenerationRequestRequired = errors.New("generation request is required")
	errEditRequestRequired       = errors.New("edit image request is required")
	errSemanticPlannerRequired   = errors.New("semantic planner is required for image editing")
	errEditTargetsRequired       = errors.New("at least one edit target is required")
	errEditTargetURLRequired     = errors.New("edit target URL is required")
	errEditPlanTargetCount       = errors.New("edit plan must contain exactly one entry for every target")
	errEditPlanTargetOutOfRange  = errors.New("edit plan target index is out of range")
	errEditPlanTargetDuplicate   = errors.New("edit plan contains a duplicate target index")
	errEditPlanPromptRequired    = errors.New("edit plan must describe every target edit")
	errEditedImageCountInvalid   = errors.New("image provider must return exactly one edited image per target")
)

func validateEditContext(editContext domain.EditContext) error {
	if len(editContext.Targets) == 0 {
		return errEditTargetsRequired
	}
	for targetIndex, target := range editContext.Targets {
		if target.URL == "" {
			return fmt.Errorf("target %d: %w", targetIndex, errEditTargetURLRequired)
		}
	}
	return nil
}

func validateEditPlan(plan domain.EditPlan, targetCount int) error {
	if len(plan.Targets) != targetCount {
		return fmt.Errorf(
			"%w: got %d entries for %d targets",
			errEditPlanTargetCount,
			len(plan.Targets),
			targetCount,
		)
	}

	seen := make([]bool, targetCount)
	for _, target := range plan.Targets {
		if target.TargetIndex < 0 || target.TargetIndex >= targetCount {
			return fmt.Errorf(
				"%w: %d",
				errEditPlanTargetOutOfRange,
				target.TargetIndex,
			)
		}
		if seen[target.TargetIndex] {
			return fmt.Errorf(
				"%w: %d",
				errEditPlanTargetDuplicate,
				target.TargetIndex,
			)
		}
		seen[target.TargetIndex] = true
	}
	for _, target := range plan.Targets {
		if buildPrompt(
			plan.StyleDescription,
			plan.SharedDescription,
			target.Description,
		) == "" {
			return fmt.Errorf(
				"%w: target %d",
				errEditPlanPromptRequired,
				target.TargetIndex,
			)
		}
	}
	return nil
}

func editTargetRequestID(requestID string, targetIndex int) string {
	return fmt.Sprintf("%s:edit-target:%d", requestID, targetIndex)
}

var _ GenerateService = (*generateService)(nil)
