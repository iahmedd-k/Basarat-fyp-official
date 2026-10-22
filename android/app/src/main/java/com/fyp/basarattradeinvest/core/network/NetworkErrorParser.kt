package com.fyp.basarattradeinvest.core.network

import com.google.gson.Gson
import com.google.gson.JsonObject
import retrofit2.Response

object NetworkErrorParser {

    private val gson = Gson()

    fun parseError(response: Response<*>): String {
        // A 5xx body from the backend is a server-side traceback (Pydantic response-model
        // validation text, stack fragments, pydantic.dev links). None of it is actionable for a
        // user, so keep it out of the UI and offer a retry instead.
        if (response.code() in 500..599) {
            return "The server couldn't complete this request (${response.code()}). Please try again."
        }

        val errorBody = response.errorBody()?.string()
        if (errorBody.isNullOrBlank()) {
            return when (response.code()) {
                400 -> "Bad Request. Please verify your inputs."
                401 -> "Unauthorized. Please log in again."
                403 -> "Access forbidden."
                404 -> "Resource not found."
                409 -> "An account with these details already exists."
                422 -> "Validation error. Please check the entered data."
                429 -> "Too many requests. Please try again in a few moments."
                else -> "An unexpected network error occurred (${response.code()})."
            }
        }

        return try {
            val jsonObject = gson.fromJson(errorBody, JsonObject::class.java)

            if (jsonObject.has("detail")) {
                val detailElement = jsonObject.get("detail")
                if (detailElement.isJsonPrimitive) {
                    detailElement.asString
                } else if (detailElement.isJsonArray) {
                    // FastAPI 422 validation errors
                    val errors = mutableListOf<String>()
                    detailElement.asJsonArray.forEach { elem ->
                        if (elem.isJsonObject) {
                            val obj = elem.asJsonObject
                            val msg = obj.get("msg")?.asString
                            val loc = obj.get("loc")?.asJsonArray
                            val field = loc?.lastOrNull()?.asString
                            if (field != null && msg != null) {
                                errors.add("$field: $msg")
                            } else if (msg != null) {
                                errors.add(msg)
                            }
                        }
                    }
                    if (errors.isNotEmpty()) errors.joinToString("\n") else "Validation failed"
                } else {
                    detailElement.toString()
                }
            } else if (jsonObject.has("error") && jsonObject.get("error").isJsonObject) {
                val errObj = jsonObject.getAsJsonObject("error")
                if (errObj.has("message") && !errObj.get("message").isJsonNull) {
                    errObj.get("message").asString
                } else {
                    errorBody
                }
            } else if (jsonObject.has("message")) {
                jsonObject.get("message").asString
            } else {
                errorBody
            }
        } catch (_: Exception) {
            errorBody.take(120)
        }
    }
}
