package com.fyp.basarattradeinvest.network

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class NetworkErrorParserTest {

    private fun error(code: Int, body: String): Response<Any> =
        Response.error(code, body.toResponseBody("application/json".toMediaTypeOrNull()))

    @Test
    fun `server side failure hides the backend traceback`() {
        val message = NetworkErrorParser.parseError(
            error(
                500,
                """{"success":false,"error":{"code":"INTERNAL_ERROR",""" +
                    """"message":"Failed to fetch alerts: 1 validation error for AlertResponse""" +
                    """ rule_id Input should be a valid string https://errors.pydantic.dev/2.13/v/string_type"}}"""
            )
        )

        assertFalse(message.contains("pydantic"))
        assertFalse(message.contains("AlertResponse"))
        assertTrue(message.contains("500"))
        assertTrue(message.contains("try again"))
    }

    @Test
    fun `client side failure still surfaces the server message`() {
        val message = NetworkErrorParser.parseError(
            error(401, """{"success":false,"error":{"code":"UNAUTHORIZED","message":"Token has expired"}}""")
        )

        assertEquals("Token has expired", message)
    }

    @Test
    fun `fastapi validation detail list is flattened to field and reason`() {
        val message = NetworkErrorParser.parseError(
            error(422, """{"detail":[{"loc":["body","symbol"],"msg":"field required","type":"value_error.missing"}]}""")
        )

        assertEquals("symbol: field required", message)
    }
}
