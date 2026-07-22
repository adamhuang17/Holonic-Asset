package echox

import (
	"errors"
	"net/http"

	"github.com/labstack/echo/v4"
)

const UserClaimsKey = "user_claims"


type HandlerFunc[Resp any] func(echo.Context) (Resp, error)

type ReqHandlerFunc[Req any, Resp any] func(
	echo.Context,
	Req,
) (Resp, error)

type ClaimsHandlerFunc[Claims any, Resp any] func(
	echo.Context,
	Claims,
) (Resp, error)

type ClaimsReqHandlerFunc[
	Req any,
	Claims any,
	Resp any,
] func(
	echo.Context,
	Req,
	Claims,
) (Resp, error)

func Wrap[Resp any](fn HandlerFunc[Resp]) echo.HandlerFunc {
	return func(c echo.Context) error {
		resp, err := fn(c)
		if err != nil {
			return err
		}
		return c.JSON(http.StatusOK, resp)
	}
}

func WrapReq[Req any, Resp any](fn ReqHandlerFunc[Req, Resp]) echo.HandlerFunc {
	return func(c echo.Context) error {

		var req Req

		if err := Bind(c, &req); err != nil {
			return err
		}

		resp, err := fn(c, req)
		if err != nil {
			return err
		}

		return c.JSON(http.StatusOK, resp)
	}
}

func WrapClaims[Claims any, Resp any](fn ClaimsHandlerFunc[Claims, Resp]) echo.HandlerFunc {
	return func(c echo.Context) error {

		claims, err := GetClaims[Claims](c)
		if err != nil {
			return err
		}

		resp, err := fn(c, claims)
		if err != nil {
			return err
		}

		return c.JSON(http.StatusOK, resp)
	}
}

func WrapClaimsAndReq[
	Req any,
	Claims any,
	Resp any,
](fn ClaimsReqHandlerFunc[Req, Claims, Resp]) echo.HandlerFunc {

	return func(c echo.Context) error {

		var req Req

		if err := Bind(c, &req); err != nil {
			return err
		}

		claims, err := GetClaims[Claims](c)
		if err != nil {
			return err
		}

		resp, err := fn(c, req, claims)
		if err != nil {
			return err
		}

		return c.JSON(http.StatusOK, resp)
	}
}

func Bind(c echo.Context, req any) error {

	if err := c.Bind(req); err != nil {
		return err
	}

	if c.Echo().Validator != nil {
		if err := c.Validate(req); err != nil {
			return err
		}
	}

	return nil
}

func SetClaims[T any](c echo.Context, claims T) {
	c.Set(UserClaimsKey, claims)
}

func GetClaims[T any](c echo.Context) (T, error) {

	var claims T

	raw := c.Get(UserClaimsKey)
	if raw == nil {
		return claims, errors.New("claims not found")
	}

	v, ok := raw.(T)
	if !ok {
		return claims, errors.New("claims type mismatch")
	}

	return v, nil
}