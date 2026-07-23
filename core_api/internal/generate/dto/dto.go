package dto

import "github.com/1024XEngineer/Holonic-Asset/internal/generate/domain"

// Size describes the requested output dimensions in pixels.
type Size struct {
	Width  uint `json:"width"`
	Height uint `json:"height"`
}

// ImageGenerationInput contains provider-neutral image generation parameters.
type ImageGenerationInput struct {
	Prompt        string   `json:"prompt"`
	ReferenceURLs []string `json:"referenceUrls,omitempty"`
	Size          Size     `json:"size"`
}

// GenerateImageRequest describes one internal image generation command.
type GenerateImageRequest struct {
	RequestID string                `json:"requestId"`
	Kind      domain.GenerationKind `json:"kind"`
	ImageGenerationInput
}

// EditImageRequest describes one internal image edit command.
type EditImageRequest struct {
	RequestID  string                `json:"requestId"`
	Kind       domain.GenerationKind `json:"kind"`
	Prompt     string                `json:"prompt"`
	TargetURLs []string              `json:"targetUrls"`
}

// ImageResult contains the images produced by a synchronous generation or edit.
type ImageResult struct {
	OutputURLs []string `json:"outputUrls"`
}
