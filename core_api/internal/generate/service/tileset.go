package service

import (
	"fmt"

	"github.com/1024XEngineer/Holonic-Asset/internal/generate/dto"
)

type tileSetStrategy struct {
	baseGenerationStrategy
}

func newTileSetStrategy(tools []ImageTool) generationStrategy {
	return &tileSetStrategy{baseGenerationStrategy: baseGenerationStrategy{tools: tools}}
}

func assembleTileSetInput(request *dto.GenerateTileSetRequest) generationInput {
	input := assembleGenerationInput(request.Context)
	specification := request.Specification
	input.specification = specification
	input.promptParts = append(
		input.promptParts,
		fmt.Sprintf("Tile set item: %s", specification.Item.Name),
		specification.Item.Description,
		fmt.Sprintf(
			"Tile set grid size: %d x %d",
			specification.GridSize.Width,
			specification.GridSize.Height,
		),
		fmt.Sprintf(
			"Tile set item span: %d columns x %d rows",
			specification.Item.SpanColumns,
			specification.Item.SpanRows,
		),
	)
	input.references = append(input.references, specification.Item.References...)
	return input
}
