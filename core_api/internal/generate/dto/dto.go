package dto

import "github.com/1024XEngineer/Holonic-Asset/internal/generate/domain"

type BaseGenerationRequest struct {
	RequestID string                   `json:"requestId"`
	Context   domain.GenerationContext `json:"context"`
}

type GenerateImageRequest struct {
	BaseGenerationRequest
}

type GenerateCharacterRequest struct {
	BaseGenerationRequest
}

type GenerateTileSetRequest struct {
	BaseGenerationRequest
	Specification domain.TileSetSpecification `json:"specification"`
}

type GenerateObjectRequest struct {
	BaseGenerationRequest
}

type GenerateSceneryRequest struct {
	BaseGenerationRequest
}

type GenerateAnimationRequest struct {
	BaseGenerationRequest
	Specification domain.AnimationSpecification `json:"specification"`
}

type GenerateUIRequest struct {
	BaseGenerationRequest
}

// EditImageRequest describes one internal image edit command.
type EditImageRequest struct {
	RequestID string                `json:"requestId"`
	Kind      domain.GenerationKind `json:"kind"`
	Context   domain.EditContext    `json:"context"`
}

// ImageResult contains images produced by a synchronous generation.
type ImageResult struct {
	OutputURLs []string `json:"outputUrls"`
}

// EditedImage maps one edited output back to the target in EditContext.Targets.
type EditedImage struct {
	TargetIndex int    `json:"targetIndex"`
	OutputURL   string `json:"outputUrl"`
}

// EditImageResult preserves the target identity of every edited image.
type EditImageResult struct {
	EditedImages []EditedImage `json:"editedImages"`
}
