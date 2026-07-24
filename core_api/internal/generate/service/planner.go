package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	aiprovider "github.com/1024XEngineer/Holonic-Asset/internal/ai/provider"
	"github.com/1024XEngineer/Holonic-Asset/internal/generate/domain"
)

// SemanticPlanner translates one shared edit instruction into one edit per
// target. TargetIndex refers to the position in EditContext.Targets.
type SemanticPlanner interface {
	PlanEdit(
		ctx context.Context,
		requestID string,
		model string,
		editContext domain.EditContext,
	) (domain.EditPlan, error)
}

// LanguageProvider is the provider capability needed by the semantic planner.
type LanguageProvider interface {
	Chat(ctx context.Context, request *aiprovider.LLMRequest) (*aiprovider.LLMResponse, error)
}

type semanticPlanner struct {
	provider LanguageProvider
}

type editPlanPayload struct {
	StyleDescription  string              `json:"styleDescription"`
	SharedDescription string              `json:"sharedDescription"`
	Targets           []targetEditPayload `json:"targets"`
}

type targetEditPayload struct {
	TargetIndex int    `json:"targetIndex"`
	Description string `json:"description"`
}

var (
	errEditPlanResponseRequired = errors.New("semantic planner returned no edit plan")
	editPlanResponseFormat      = json.RawMessage(`{
		"type": "json_schema",
		"json_schema": {
			"name": "edit_plan",
			"strict": true,
			"schema": {
				"type": "object",
				"additionalProperties": false,
				"properties": {
					"styleDescription": {"type": "string"},
					"sharedDescription": {"type": "string"},
					"targets": {
						"type": "array",
						"items": {
							"type": "object",
							"additionalProperties": false,
							"properties": {
								"targetIndex": {"type": "integer", "minimum": 0},
								"description": {"type": "string"}
							},
							"required": ["targetIndex", "description"]
						}
					}
				},
				"required": ["styleDescription", "sharedDescription", "targets"]
			}
		}
	}`)
)

// NewSemanticPlanner creates an LLM-backed planner for per-target image edits.
func NewSemanticPlanner(provider LanguageProvider) SemanticPlanner {
	return &semanticPlanner{provider: provider}
}

func (p *semanticPlanner) PlanEdit(
	ctx context.Context,
	requestID string,
	model string,
	editContext domain.EditContext,
) (domain.EditPlan, error) {
	request, err := buildEditPlanRequest(requestID, model, editContext)
	if err != nil {
		return domain.EditPlan{}, err
	}
	response, err := p.provider.Chat(ctx, request)
	if err != nil {
		return domain.EditPlan{}, err
	}
	payload, err := decodeEditPlan(response)
	if err != nil {
		return domain.EditPlan{}, err
	}

	plan := domain.EditPlan{
		StyleDescription:  payload.StyleDescription,
		SharedDescription: payload.SharedDescription,
		Targets:           make([]domain.TargetEdit, 0, len(payload.Targets)),
	}
	for _, target := range payload.Targets {
		plan.Targets = append(plan.Targets, domain.TargetEdit{
			TargetIndex: target.TargetIndex,
			Description: target.Description,
		})
	}
	return plan, nil
}

func buildEditPlanRequest(
	requestID string,
	model string,
	editContext domain.EditContext,
) (*aiprovider.LLMRequest, error) {
	planningContext, err := json.Marshal(struct {
		ProjectStyle string `json:"projectStyle"`
		Asset        string `json:"assetDescription"`
		Instruction  string `json:"instruction"`
		TargetCount  int    `json:"targetCount"`
	}{
		ProjectStyle: editContext.Project.Style,
		Asset:        editContext.Asset.Description,
		Instruction:  editContext.Instruction,
		TargetCount:  len(editContext.Targets),
	})
	if err != nil {
		return nil, fmt.Errorf("encode edit planning context: %w", err)
	}

	userContent := []aiprovider.ContentPart{{
		Type: aiprovider.ContentPartText,
		Text: string(planningContext),
	}}
	for targetIndex, target := range editContext.Targets {
		userContent = append(
			userContent,
			aiprovider.ContentPart{
				Type: aiprovider.ContentPartText,
				Text: fmt.Sprintf("Target index: %d", targetIndex),
			},
			aiprovider.ContentPart{
				Type: aiprovider.ContentPartImageURL,
				URL:  target.URL,
			},
		)
	}

	return &aiprovider.LLMRequest{
		RequestID: requestID + ":edit-plan",
		Model:     model,
		Messages: []aiprovider.LLMMessage{
			{
				Role: aiprovider.MessageRoleSystem,
				Content: []aiprovider.ContentPart{{
					Type: aiprovider.ContentPartText,
					Text: "Create a semantic image-edit plan. Preserve the requested project style and shared asset identity. Return exactly one target entry for every supplied target index. Put common edit requirements in sharedDescription and only target-specific requirements in each target description.",
				}},
			},
			{
				Role:    aiprovider.MessageRoleUser,
				Content: userContent,
			},
		},
		ResponseFormat: append(json.RawMessage(nil), editPlanResponseFormat...),
	}, nil
}

func decodeEditPlan(response *aiprovider.LLMResponse) (editPlanPayload, error) {
	if response == nil {
		return editPlanPayload{}, errEditPlanResponseRequired
	}

	var textParts []string
	for _, part := range response.Message.Content {
		if part.Type == aiprovider.ContentPartText && strings.TrimSpace(part.Text) != "" {
			textParts = append(textParts, part.Text)
		}
	}
	if len(textParts) == 0 {
		return editPlanPayload{}, errEditPlanResponseRequired
	}

	var payload editPlanPayload
	if err := json.Unmarshal([]byte(strings.Join(textParts, "")), &payload); err != nil {
		return editPlanPayload{}, fmt.Errorf("decode semantic edit plan: %w", err)
	}
	return payload, nil
}

var _ SemanticPlanner = (*semanticPlanner)(nil)
